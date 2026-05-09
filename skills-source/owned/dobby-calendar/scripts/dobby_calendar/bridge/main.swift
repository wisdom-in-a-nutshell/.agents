import EventKit
import Foundation
import Darwin

let schemaVersion = "1.0"
let bridgeVersion = "0.1.0"

struct BridgeError: Error {
    let code: String
    let message: String
    let hint: String
    let retryable: Bool

    init(_ code: String, _ message: String, hint: String = "", retryable: Bool = false) {
        self.code = code
        self.message = message
        self.hint = hint
        self.retryable = retryable
    }
}

final class Clock {
    let start = Date()
    func durationMs() -> Int { Int(Date().timeIntervalSince(start) * 1000) }
}

func utcTimestamp() -> String {
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime]
    return formatter.string(from: Date())
}

func requestID() -> String { UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased() }

func jsonData(_ object: Any) -> Data {
    return (try? JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted, .sortedKeys])) ?? Data("{}".utf8)
}

func emit(_ envelope: [String: Any], exitCode: Int32) -> Never {
    FileHandle.standardOutput.write(jsonData(envelope))
    FileHandle.standardOutput.write(Data("\n".utf8))
    Foundation.exit(exitCode)
}

func exitCode(for code: String) -> Int32 {
    switch code {
    case "E_VALIDATION": return 2
    case "E_AUTH": return 3
    case "E_DEPENDENCY": return 4
    case "E_TIMEOUT": return 5
    default: return 1
    }
}

func okEnvelope(command: String, data: Any, clock: Clock, requestId: String) -> [String: Any] {
    return [
        "schema_version": schemaVersion,
        "command": command,
        "status": "ok",
        "data": data,
        "error": NSNull(),
        "meta": [
            "request_id": requestId,
            "duration_ms": clock.durationMs(),
            "timestamp_utc": utcTimestamp(),
            "backend": "eventkit",
            "bridge_version": bridgeVersion
        ]
    ]
}

func errEnvelope(command: String, error: BridgeError, clock: Clock, requestId: String) -> [String: Any] {
    return [
        "schema_version": schemaVersion,
        "command": command,
        "status": "error",
        "data": NSNull(),
        "error": [
            "code": error.code,
            "message": error.message,
            "retryable": error.retryable,
            "hint": error.hint
        ],
        "meta": [
            "request_id": requestId,
            "duration_ms": clock.durationMs(),
            "timestamp_utc": utcTimestamp(),
            "backend": "eventkit",
            "bridge_version": bridgeVersion
        ]
    ]
}

func usage() -> String {
    return """
Dobby Calendar Bridge \(bridgeVersion)

Usage:
  DobbyCalendarBridge serve [--socket <path>]
  DobbyCalendarBridge send <command> [args...] [--socket <path>]
  DobbyCalendarBridge doctor [--request-access] [--no-input]
  DobbyCalendarBridge calendars [--no-input]
  DobbyCalendarBridge list --from <date> --to <date> [--query <text>] [--calendar <name>|--all-calendars] [--limit <n>] [--no-recurring] [--no-input]
  DobbyCalendarBridge add --title <title> --start <date> [--end <date>] --calendar <name> [--all-day] [--location <text>] [--notes <text>] [--url <url>] [--repeat daily|weekly|monthly|yearly] [--repeat-until <date>] [--no-alert] [--no-input]
  DobbyCalendarBridge update --id <event-id> [--title <title>] [--start <date>] [--end <date>] [--calendar <name>] [--location <text>] [--notes <text>] [--url <url>] [--no-alert] [--no-input]
  DobbyCalendarBridge --version

Output is always one JSON envelope on stdout. Diagnostics go to stderr.
"""
}

struct ParsedArgs {
    let command: String
    var values: [String: String] = [:]
    var flags: Set<String> = []
}

func parseArgs(_ raw: [String]) throws -> ParsedArgs {
    var args = raw
    if args.contains("--version") || args.contains("-v") {
        return ParsedArgs(command: "version")
    }
    if args.contains("--help") || args.contains("-h") || args.isEmpty {
        return ParsedArgs(command: "help")
    }
    let command = args.removeFirst()
    let knownCommands = ["doctor", "calendars", "list", "add", "update"]
    guard knownCommands.contains(command) else {
        throw BridgeError("E_VALIDATION", "unknown command: \(command)", hint: usage())
    }
    var parsed = ParsedArgs(command: command)
    var i = 0
    while i < args.count {
        let arg = args[i]
        switch arg {
        case "--request-access", "--all-calendars", "--all-day", "--no-alert", "--no-recurring", "--no-input":
            parsed.flags.insert(String(arg.dropFirst(2)))
            i += 1
        case "--from", "--to", "--query", "--calendar", "--limit", "--title", "--start", "--end", "--location", "--notes", "--url", "--repeat", "--repeat-until", "--id":
            guard i + 1 < args.count else {
                throw BridgeError("E_VALIDATION", "missing value for \(arg)", hint: usage())
            }
            parsed.values[String(arg.dropFirst(2))] = args[i + 1]
            i += 2
        default:
            throw BridgeError("E_VALIDATION", "unknown argument: \(arg)", hint: usage())
        }
    }
    return parsed
}

func requireValue(_ args: ParsedArgs, _ key: String) throws -> String {
    guard let value = args.values[key], !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
        throw BridgeError("E_VALIDATION", "--\(key) is required", hint: usage())
    }
    return value
}

func authStatusName(_ status: EKAuthorizationStatus) -> String {
    switch status {
    case .notDetermined: return "not_determined"
    case .restricted: return "restricted"
    case .denied: return "denied"
    case .authorized: return "authorized"
    case .fullAccess: return "full_access"
    case .writeOnly: return "write_only"
    @unknown default: return "unknown"
    }
}

final class CalendarBridge {
    private let store = EKEventStore()
    private let calendar = Calendar.current

    func ensureAccess(requestIfNeeded: Bool) throws {
        let status = EKEventStore.authorizationStatus(for: .event)
        switch status {
        case .authorized, .fullAccess:
            return
        case .notDetermined:
            guard requestIfNeeded else {
                throw BridgeError(
                    "E_AUTH",
                    "Calendar access has not been granted to Dobby Calendar Bridge",
                    hint: "Run ~/.agents/skills-source/owned/dobby-calendar/scripts/dobby_calendar/bridge/install --request-access, then grant Full Calendar Access in System Settings > Privacy & Security > Calendars."
                )
            }
            var done = false
            var granted = false
            var requestError: Error?
            if #available(macOS 14.0, *) {
                store.requestFullAccessToEvents { ok, error in
                    granted = ok
                    requestError = error
                    done = true
                }
            } else {
                store.requestAccess(to: .event) { ok, error in
                    granted = ok
                    requestError = error
                    done = true
                }
            }
            let deadline = Date().addingTimeInterval(120)
            while !done && Date() < deadline {
                RunLoop.current.run(mode: .default, before: Date().addingTimeInterval(0.1))
            }
            if granted { return }
            let detail = requestError.map { ": \($0.localizedDescription)" } ?? ""
            throw BridgeError(
                "E_AUTH",
                "Calendar access was not granted\(detail)",
                hint: "Grant Full Calendar Access to Dobby Calendar Bridge in System Settings > Privacy & Security > Calendars."
            )
        case .denied, .restricted, .writeOnly:
            throw BridgeError(
                "E_AUTH",
                "Calendar access is \(authStatusName(status)) for Dobby Calendar Bridge",
                hint: "Grant Full Calendar Access to Dobby Calendar Bridge in System Settings > Privacy & Security > Calendars."
            )
        @unknown default:
            throw BridgeError("E_AUTH", "Calendar authorization status is unknown", hint: "Check macOS Calendar privacy settings for Dobby Calendar Bridge.")
        }
    }

    func doctor(requestAccess: Bool) throws -> [String: Any] {
        let statusBefore = EKEventStore.authorizationStatus(for: .event)
        var accessOk = false
        var accessDetail = authStatusName(statusBefore)
        do {
            try ensureAccess(requestIfNeeded: requestAccess)
            accessOk = true
            accessDetail = authStatusName(EKEventStore.authorizationStatus(for: .event))
        } catch let error as BridgeError {
            accessDetail = error.message
            if requestAccess { throw error }
        }
        var calendarsCount = 0
        if accessOk {
            calendarsCount = store.calendars(for: .event).count
        }
        return [
            "ok": accessOk,
            "backend": "eventkit",
            "bundle_id": Bundle.main.bundleIdentifier ?? "unknown",
            "authorization_status": authStatusName(EKEventStore.authorizationStatus(for: .event)),
            "checks": [
                ["name": "eventkit_access", "ok": accessOk, "detail": accessDetail],
                ["name": "visible_calendars", "ok": accessOk, "detail": accessOk ? "\(calendarsCount) calendars" : "skipped"]
            ]
        ]
    }

    func calendars() throws -> [[String: Any]] {
        try ensureAccess(requestIfNeeded: false)
        return store.calendars(for: .event)
            .sorted { lhs, rhs in lhs.title.localizedCaseInsensitiveCompare(rhs.title) == .orderedAscending }
            .map(calendarInfo)
    }

    func listEvents(from fromText: String, to toText: String, query: String?, calendarName: String?, allCalendars: Bool, limit: Int?, noRecurring: Bool) throws -> [[String: Any]] {
        try ensureAccess(requestIfNeeded: false)
        let start = try parseDate(fromText, role: .rangeStart)
        let end = try parseDate(toText, role: .rangeEnd)
        if end <= start {
            throw BridgeError("E_VALIDATION", "--to must be after --from")
        }
        let selectedCalendars = try calendarsForRead(calendarName: calendarName, allCalendars: allCalendars)
        let predicate = store.predicateForEvents(withStart: start, end: end, calendars: selectedCalendars)
        var events = store.events(matching: predicate)
        if noRecurring {
            events = events.filter { !$0.hasRecurrenceRules }
        }
        if let query, !query.isEmpty {
            let needle = query.lowercased()
            events = events.filter { event in
                [event.title, event.location, event.notes]
                    .compactMap { $0?.lowercased() }
                    .contains { $0.contains(needle) }
            }
        }
        events.sort { lhs, rhs in
            if lhs.startDate == rhs.startDate { return lhs.title < rhs.title }
            return lhs.startDate < rhs.startDate
        }
        if let limit, limit >= 0, events.count > limit {
            events = Array(events.prefix(limit))
        }
        return events.map(eventInfo)
    }

    func addEvent(args: ParsedArgs) throws -> [String: Any] {
        try ensureAccess(requestIfNeeded: false)
        let title = try requireValue(args, "title")
        let startText = try requireValue(args, "start")
        let calendarName = try requireValue(args, "calendar")
        let targetCalendar = try writableCalendar(named: calendarName)
        let allDay = args.flags.contains("all-day")
        let start = try parseDate(startText, role: .eventStart)
        let end: Date
        if let endText = args.values["end"], !endText.isEmpty {
            end = try parseDate(endText, role: allDay ? .allDayEnd : .eventEnd)
        } else {
            end = allDay ? calendar.date(byAdding: .day, value: 1, to: calendar.startOfDay(for: start))! : calendar.date(byAdding: .hour, value: 1, to: start)!
        }
        if end <= start {
            throw BridgeError("E_VALIDATION", "event end must be after start")
        }

        let event = EKEvent(eventStore: store)
        event.title = title
        event.calendar = targetCalendar
        event.startDate = allDay ? calendar.startOfDay(for: start) : start
        event.endDate = end
        event.isAllDay = allDay
        if let location = args.values["location"] { event.location = location }
        if let notes = args.values["notes"] { event.notes = notes }
        if let urlText = args.values["url"], let url = URL(string: urlText) { event.url = url }
        if args.flags.contains("no-alert") {
            event.alarms = []
        }
        if let frequency = args.values["repeat"] {
            event.recurrenceRules = [try recurrenceRule(frequency: frequency, untilText: args.values["repeat-until"])]
        }
        do {
            try store.save(event, span: .thisEvent, commit: true)
        } catch {
            throw BridgeError("E_RUNTIME", "failed to save event: \(error.localizedDescription)")
        }
        return eventInfo(event)
    }

    func updateEvent(args: ParsedArgs) throws -> [String: Any] {
        try ensureAccess(requestIfNeeded: false)
        let id = try requireValue(args, "id")
        guard let event = store.event(withIdentifier: id) else {
            throw BridgeError("E_NOT_FOUND", "event not found: \(id)")
        }

        if let title = args.values["title"] { event.title = title }
        if let calendarName = args.values["calendar"] {
            event.calendar = try writableCalendar(named: calendarName)
        }
        if let startText = args.values["start"] {
            event.startDate = try parseDate(startText, role: .eventStart)
        }
        if let endText = args.values["end"] {
            event.endDate = try parseDate(endText, role: event.isAllDay ? .allDayEnd : .eventEnd)
        }
        if event.endDate <= event.startDate {
            throw BridgeError("E_VALIDATION", "event end must be after start")
        }
        if let location = args.values["location"] { event.location = location }
        if let notes = args.values["notes"] { event.notes = notes }
        if let urlText = args.values["url"] {
            event.url = urlText.isEmpty ? nil : URL(string: urlText)
        }
        if args.flags.contains("no-alert") {
            event.alarms = []
        }
        if let frequency = args.values["repeat"] {
            if frequency == "none" {
                event.recurrenceRules = nil
            } else {
                event.recurrenceRules = [try recurrenceRule(frequency: frequency, untilText: args.values["repeat-until"])]
            }
        }
        do {
            try store.save(event, span: .thisEvent, commit: true)
        } catch {
            throw BridgeError("E_RUNTIME", "failed to update event: \(error.localizedDescription)")
        }
        return eventInfo(event)
    }

    private enum DateRole { case rangeStart, rangeEnd, eventStart, eventEnd, allDayEnd }

    private func parseDate(_ text: String, role: DateRole) throws -> Date {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { throw BridgeError("E_VALIDATION", "date value cannot be empty") }

        if let parsed = parseISODate(trimmed) {
            switch role {
            case .rangeEnd where parsed.dateOnly:
                return calendar.date(byAdding: .day, value: 1, to: parsed.date)!
            case .allDayEnd where parsed.dateOnly:
                return calendar.startOfDay(for: parsed.date)
            default:
                return parsed.date
            }
        }

        let lowered = trimmed.lowercased()
        if lowered == "today" {
            let day = calendar.startOfDay(for: Date())
            return role == .rangeEnd ? calendar.date(byAdding: .day, value: 1, to: day)! : day
        }
        if lowered == "tomorrow" {
            let day = calendar.date(byAdding: .day, value: 1, to: calendar.startOfDay(for: Date()))!
            return role == .rangeEnd ? calendar.date(byAdding: .day, value: 1, to: day)! : day
        }
        if lowered == "now" { return Date() }

        if let detected = detectNaturalDate(trimmed) {
            return detected
        }

        throw BridgeError("E_VALIDATION", "could not parse date: \(text)", hint: "Use ISO dates like 2026-04-30 or 2026-04-30 11:00.")
    }

    private func parseISODate(_ text: String) -> (date: Date, dateOnly: Bool)? {
        let posix = Locale(identifier: "en_US_POSIX")
        let tz = TimeZone.current
        let formats: [(String, Bool)] = [
            ("yyyy-MM-dd", true),
            ("yyyy-MM-dd HH:mm", false),
            ("yyyy-MM-dd HH:mm:ss", false),
            ("yyyy-MM-dd'T'HH:mm", false),
            ("yyyy-MM-dd'T'HH:mm:ss", false),
            ("yyyy-MM-dd'T'HH:mm:ssXXXXX", false),
            ("yyyy-MM-dd'T'HH:mm:ss.SSSXXXXX", false)
        ]
        for (format, dateOnly) in formats {
            let formatter = DateFormatter()
            formatter.locale = posix
            formatter.timeZone = tz
            formatter.dateFormat = format
            if let date = formatter.date(from: text) {
                return (dateOnly ? calendar.startOfDay(for: date) : date, dateOnly)
            }
        }
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = iso.date(from: text) { return (date, false) }
        iso.formatOptions = [.withInternetDateTime]
        if let date = iso.date(from: text) { return (date, false) }
        return nil
    }

    private func detectNaturalDate(_ text: String) -> Date? {
        guard let detector = try? NSDataDetector(types: NSTextCheckingResult.CheckingType.date.rawValue) else { return nil }
        let range = NSRange(text.startIndex..<text.endIndex, in: text)
        let matches = detector.matches(in: text, options: [], range: range)
        return matches.first?.date
    }

    private func calendarsForRead(calendarName: String?, allCalendars: Bool) throws -> [EKCalendar]? {
        if allCalendars { return nil }
        guard let calendarName, !calendarName.isEmpty else {
            throw BridgeError("E_VALIDATION", "calendar is required unless --all-calendars is set")
        }
        let matches = store.calendars(for: .event).filter { $0.title == calendarName }
        guard !matches.isEmpty else {
            throw BridgeError("E_NOT_FOUND", "calendar not found: \(calendarName)")
        }
        return matches
    }

    private func writableCalendar(named name: String) throws -> EKCalendar {
        let matches = store.calendars(for: .event).filter { $0.title == name }
        guard let calendar = matches.first else {
            throw BridgeError("E_NOT_FOUND", "calendar not found: \(name)")
        }
        guard calendar.allowsContentModifications else {
            throw BridgeError("E_AUTH", "calendar is read-only: \(name)")
        }
        return calendar
    }

    private func calendarInfo(_ calendar: EKCalendar) -> [String: Any] {
        return [
            "id": calendar.calendarIdentifier,
            "title": calendar.title,
            "source": calendar.source.title,
            "source_type": String(describing: calendar.source.sourceType),
            "readOnly": !calendar.allowsContentModifications,
            "allowsContentModifications": calendar.allowsContentModifications,
            "type": String(describing: calendar.type)
        ]
    }

    private func eventInfo(_ event: EKEvent) -> [String: Any] {
        var info: [String: Any] = [
            "id": event.eventIdentifier ?? "",
            "title": event.title ?? "",
            "calendar": event.calendar?.title ?? "",
            "calendar_id": event.calendar?.calendarIdentifier ?? "",
            "start_date": formatDate(event.startDate, allDay: event.isAllDay),
            "end_date": formatDate(event.endDate, allDay: event.isAllDay),
            "start": formatDateTime(event.startDate),
            "end": formatDateTime(event.endDate),
            "all_day": event.isAllDay,
            "is_all_day": event.isAllDay,
            "has_recurrence_rules": event.hasRecurrenceRules
        ]
        if let location = event.location, !location.isEmpty { info["location"] = location }
        if let notes = event.notes, !notes.isEmpty { info["notes"] = notes }
        if let url = event.url { info["url"] = url.absoluteString }
        return info
    }

    private func formatDate(_ date: Date, allDay: Bool) -> String {
        if allDay {
            let formatter = DateFormatter()
            formatter.locale = Locale(identifier: "en_US_POSIX")
            formatter.timeZone = TimeZone.current
            formatter.dateFormat = "yyyy-MM-dd"
            return formatter.string(from: date)
        }
        return formatDateTime(date)
    }

    private func formatDateTime(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone.current
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ssXXXXX"
        return formatter.string(from: date)
    }

    private func recurrenceRule(frequency: String, untilText: String?) throws -> EKRecurrenceRule {
        let freq: EKRecurrenceFrequency
        switch frequency {
        case "daily": freq = .daily
        case "weekly": freq = .weekly
        case "monthly": freq = .monthly
        case "yearly": freq = .yearly
        default: throw BridgeError("E_VALIDATION", "invalid repeat frequency: \(frequency)")
        }
        let end: EKRecurrenceEnd?
        if let untilText, !untilText.isEmpty {
            end = EKRecurrenceEnd(end: try parseDate(untilText, role: .rangeEnd))
        } else {
            end = nil
        }
        return EKRecurrenceRule(recurrenceWith: freq, interval: 1, end: end)
    }
}

func defaultSocketPath() -> String {
    return NSHomeDirectory() + "/Library/Application Support/DobbyCalendarBridge/bridge.sock"
}

func parseSocketFlag(_ args: inout [String]) throws -> String {
    var socketPath = defaultSocketPath()
    var cleaned: [String] = []
    var i = 0
    while i < args.count {
        if args[i] == "--socket" {
            guard i + 1 < args.count else {
                throw BridgeError("E_VALIDATION", "missing value for --socket")
            }
            socketPath = args[i + 1]
            i += 2
        } else {
            cleaned.append(args[i])
            i += 1
        }
    }
    args = cleaned
    return socketPath
}

func executeParsed(_ parsed: ParsedArgs) throws -> (command: String, data: Any) {
    let bridge = CalendarBridge()
    let result: Any
    switch parsed.command {
    case "doctor":
        result = try bridge.doctor(requestAccess: parsed.flags.contains("request-access") && !parsed.flags.contains("no-input"))
    case "calendars":
        let calendars = try bridge.calendars()
        result = ["count": calendars.count, "calendars": calendars]
    case "list":
        let limit: Int?
        if let rawLimit = parsed.values["limit"] {
            guard let parsedLimit = Int(rawLimit), parsedLimit >= 0 else { throw BridgeError("E_VALIDATION", "--limit must be an integer >= 0") }
            limit = parsedLimit
        } else {
            limit = nil
        }
        let events = try bridge.listEvents(
            from: requireValue(parsed, "from"),
            to: requireValue(parsed, "to"),
            query: parsed.values["query"],
            calendarName: parsed.values["calendar"],
            allCalendars: parsed.flags.contains("all-calendars"),
            limit: limit,
            noRecurring: parsed.flags.contains("no-recurring")
        )
        result = ["count": events.count, "events": events]
    case "add":
        result = try bridge.addEvent(args: parsed)
    case "update":
        result = try bridge.updateEvent(args: parsed)
    default:
        throw BridgeError("E_VALIDATION", "unknown command: \(parsed.command)", hint: usage())
    }
    return ("calendar-bridge.\(parsed.command)", result)
}

func envelopeForRawArgs(_ rawArgs: [String], requestId: String = requestID()) -> (envelope: [String: Any], exitCode: Int32) {
    let clock = Clock()
    do {
        let parsed = try parseArgs(rawArgs)
        let executed = try executeParsed(parsed)
        return (okEnvelope(command: executed.command, data: executed.data, clock: clock, requestId: requestId), 0)
    } catch let error as BridgeError {
        let command: String
        if let first = rawArgs.first, !first.hasPrefix("-") {
            command = "calendar-bridge.\(first)"
        } else {
            command = "calendar-bridge.cli"
        }
        return (errEnvelope(command: command, error: error, clock: clock, requestId: requestId), exitCode(for: error.code))
    } catch {
        let wrapped = BridgeError("E_RUNTIME", error.localizedDescription)
        return (errEnvelope(command: "calendar-bridge.cli", error: wrapped, clock: clock, requestId: requestId), 1)
    }
}

func writeEnvelope(_ envelope: [String: Any], to fd: Int32) {
    var data = jsonData(envelope)
    data.append(Data("\n".utf8))
    data.withUnsafeBytes { ptr in
        guard let base = ptr.baseAddress else { return }
        _ = Darwin.write(fd, base, data.count)
    }
}

func sockaddrForUnixPath(_ path: String) throws -> (sockaddr_un, socklen_t) {
    var addr = sockaddr_un()
    addr.sun_family = sa_family_t(AF_UNIX)
    let bytes = Array(path.utf8)
    let maxPath = MemoryLayout.size(ofValue: addr.sun_path)
    guard bytes.count < maxPath else {
        throw BridgeError("E_VALIDATION", "socket path too long: \(path)")
    }
    withUnsafeMutableBytes(of: &addr.sun_path) { raw in
        for idx in raw.indices { raw[idx] = 0 }
        for (idx, byte) in bytes.enumerated() {
            raw[idx] = byte
        }
    }
    let length = socklen_t(MemoryLayout<sockaddr_un>.offset(of: \.sun_path)! + bytes.count + 1)
    return (addr, length)
}

func handleConnection(_ clientFd: Int32) {
    defer { Darwin.close(clientFd) }
    var buffer = [UInt8](repeating: 0, count: 4096)
    var data = Data()
    while data.count < 1_048_576 {
        let n = Darwin.read(clientFd, &buffer, buffer.count)
        if n <= 0 { break }
        data.append(buffer, count: n)
        if buffer.prefix(n).contains(10) { break }
    }
    let requestId: String
    let rawArgs: [String]
    do {
        let object = try JSONSerialization.jsonObject(with: data, options: [])
        guard let dict = object as? [String: Any] else {
            throw BridgeError("E_VALIDATION", "request must be a JSON object")
        }
        requestId = dict["request_id"] as? String ?? requestID()
        guard let command = dict["command"] as? String, !command.isEmpty else {
            throw BridgeError("E_VALIDATION", "request.command is required")
        }
        let args = dict["args"] as? [String] ?? []
        rawArgs = [command] + args
    } catch let error as BridgeError {
        let envelope = errEnvelope(command: "calendar-bridge.request", error: error, clock: Clock(), requestId: requestID())
        writeEnvelope(envelope, to: clientFd)
        return
    } catch {
        let wrapped = BridgeError("E_VALIDATION", "invalid request JSON: \(error.localizedDescription)")
        let envelope = errEnvelope(command: "calendar-bridge.request", error: wrapped, clock: Clock(), requestId: requestID())
        writeEnvelope(envelope, to: clientFd)
        return
    }
    let response = envelopeForRawArgs(rawArgs, requestId: requestId)
    writeEnvelope(response.envelope, to: clientFd)
}

func serve(socketPath: String) throws -> Never {
    let parent = URL(fileURLWithPath: socketPath).deletingLastPathComponent().path
    try FileManager.default.createDirectory(atPath: parent, withIntermediateDirectories: true)
    unlink(socketPath)

    let fd = Darwin.socket(AF_UNIX, SOCK_STREAM, 0)
    guard fd >= 0 else { throw BridgeError("E_RUNTIME", "failed to create unix socket") }

    var (addr, len) = try sockaddrForUnixPath(socketPath)
    let bindResult = withUnsafePointer(to: &addr) {
        $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
            Darwin.bind(fd, $0, len)
        }
    }
    guard bindResult == 0 else {
        Darwin.close(fd)
        throw BridgeError("E_RUNTIME", "failed to bind socket at \(socketPath)")
    }
    chmod(socketPath, S_IRUSR | S_IWUSR)
    guard Darwin.listen(fd, 16) == 0 else {
        Darwin.close(fd)
        throw BridgeError("E_RUNTIME", "failed to listen on socket")
    }

    while true {
        let client = Darwin.accept(fd, nil, nil)
        if client >= 0 {
            DispatchQueue.global(qos: .userInitiated).async {
                handleConnection(client)
            }
        }
    }
}

func send(socketPath: String, rawArgs: [String]) throws -> Never {
    guard !rawArgs.isEmpty else {
        throw BridgeError("E_VALIDATION", "send requires a bridge command", hint: usage())
    }
    let fd = Darwin.socket(AF_UNIX, SOCK_STREAM, 0)
    guard fd >= 0 else { throw BridgeError("E_RUNTIME", "failed to create unix socket") }
    var (addr, len) = try sockaddrForUnixPath(socketPath)
    let connectResult = withUnsafePointer(to: &addr) {
        $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
            Darwin.connect(fd, $0, len)
        }
    }
    guard connectResult == 0 else {
        Darwin.close(fd)
        throw BridgeError("E_DEPENDENCY", "Dobby Calendar Bridge server is not running", hint: "Run ~/.agents/skills-source/owned/dobby-calendar/scripts/dobby_calendar/bridge/install --request-access")
    }
    let req: [String: Any] = [
        "schema_version": schemaVersion,
        "request_id": requestID(),
        "command": rawArgs[0],
        "args": Array(rawArgs.dropFirst())
    ]
    var requestData = jsonData(req)
    requestData.append(Data("\n".utf8))
    requestData.withUnsafeBytes { ptr in
        if let base = ptr.baseAddress {
            _ = Darwin.write(fd, base, requestData.count)
        }
    }
    shutdown(fd, SHUT_WR)
    var buffer = [UInt8](repeating: 0, count: 4096)
    var response = Data()
    while response.count < 1_048_576 {
        let n = Darwin.read(fd, &buffer, buffer.count)
        if n <= 0 { break }
        response.append(buffer, count: n)
    }
    Darwin.close(fd)
    FileHandle.standardOutput.write(response)
    if response.last != 10 {
        FileHandle.standardOutput.write(Data("\n".utf8))
    }
    if let object = try? JSONSerialization.jsonObject(with: response, options: []),
       let dict = object as? [String: Any],
       let status = dict["status"] as? String,
       status == "error",
       let err = dict["error"] as? [String: Any],
       let code = err["code"] as? String {
        Foundation.exit(exitCode(for: code))
    }
    Foundation.exit(0)
}

let clock = Clock()
let rid = requestID()

do {
    var raw = Array(CommandLine.arguments.dropFirst())
    if let first = raw.first, first == "serve" {
        raw.removeFirst()
        let socketPath = try parseSocketFlag(&raw)
        if !raw.isEmpty {
            throw BridgeError("E_VALIDATION", "serve does not accept arguments: \(raw.joined(separator: " "))", hint: usage())
        }
        try serve(socketPath: socketPath)
    }
    if let first = raw.first, first == "send" {
        raw.removeFirst()
        let socketPath = try parseSocketFlag(&raw)
        try send(socketPath: socketPath, rawArgs: raw)
    }

    let parsed = try parseArgs(raw)
    if parsed.command == "help" {
        print(usage())
        Foundation.exit(0)
    }
    if parsed.command == "version" {
        print("Dobby Calendar Bridge \(bridgeVersion)")
        Foundation.exit(0)
    }
    let executed = try executeParsed(parsed)
    emit(okEnvelope(command: executed.command, data: executed.data, clock: clock, requestId: rid), exitCode: 0)
} catch let error as BridgeError {
    let cmd: String
    if let first = CommandLine.arguments.dropFirst().first, !first.hasPrefix("-") {
        cmd = "calendar-bridge.\(first)"
    } else {
        cmd = "calendar-bridge.cli"
    }
    emit(errEnvelope(command: cmd, error: error, clock: clock, requestId: rid), exitCode: exitCode(for: error.code))
} catch {
    let wrapped = BridgeError("E_RUNTIME", error.localizedDescription)
    emit(errEnvelope(command: "calendar-bridge.cli", error: wrapped, clock: clock, requestId: rid), exitCode: 1)
}
