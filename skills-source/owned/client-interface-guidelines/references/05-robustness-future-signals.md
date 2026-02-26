### Robustness {#robustness-guidelines}

**Validate user input.**
Everywhere your program accepts data from the user, it will eventually be given bad data.
Check early and bail out before anything bad happens, and [make the errors understandable](#errors).

**Responsive is more important than fast.**
Print something to the user in <100ms.
If you’re making a network request, print something before you do it so it doesn’t hang and look broken.

**Show progress if something takes a long time.**
If your program displays no output for a while, it will look broken.
A good spinner or progress indicator can make a program appear to be faster than it is.

Ubuntu 20.04 has a nice progress bar that sticks to the bottom of the terminal.

<!-- (TK reproduce this as a code block or animated SVG) -->

If the progress bar gets stuck in one place for a long time, the user won’t know if stuff is still happening or if the program’s crashed.
It’s good to show estimated time remaining, or even just have an animated component, to reassure them that you’re still working on it.

There are many good libraries for generating progress bars.
For example, [tqdm](https://github.com/tqdm/tqdm) for Python, [schollz/progressbar](https://github.com/schollz/progressbar) for Go, and [node-progress](https://github.com/visionmedia/node-progress) for Node.js.

**Do stuff in parallel where you can, but be thoughtful about it.**
It’s already difficult to report progress in the shell; doing it for parallel processes is ten times harder.
Make sure it’s robust, and that the output isn’t confusingly interleaved.
If you can use a library, do so—this is code you don’t want to write yourself.
Libraries like [tqdm](https://github.com/tqdm/tqdm) for Python and [schollz/progressbar](https://github.com/schollz/progressbar) for Go support multiple progress bars natively.

The upside is that it can be a huge usability gain.
For example, `docker pull`’s multiple progress bars offer crucial insight into what’s going on.

```
$ docker image pull ruby
Using default tag: latest
latest: Pulling from library/ruby
6c33745f49b4: Pull complete 
ef072fc32a84: Extracting [================================================>  ]  7.569MB/7.812MB
c0afb8e68e0b: Download complete 
d599c07d28e6: Download complete 
f2ecc74db11a: Downloading [=======================>                           ]  89.11MB/192.3MB
3568445c8bf2: Download complete 
b0efebc74f25: Downloading [===========================================>       ]  19.88MB/22.88MB
9cb1ba6838a0: Download complete 
```

One thing to be aware of: hiding logs behind progress bars when things go _well_ makes it much easier for the user to understand what’s going on, but if there is an error, make sure you print out the logs.
Otherwise, it will be very hard to debug.

**Make things time out.**
Allow network timeouts to be configured, and have a reasonable default so it doesn’t hang forever.

**Make it recoverable.**
If the program fails for some transient reason (e.g. the internet connection went down), you should be able to hit `<up>` and `<enter>` and it should pick up from where it left off.

**Make it crash-only.**
This is the next step up from idempotence.
If you can avoid needing to do any cleanup after operations, or you can defer that cleanup to the next run, your program can exit immediately on failure or interruption.
This makes it both more robust and more responsive.

_Citation: [Crash-only software: More than meets the eye](https://lwn.net/Articles/191059/)._

**People are going to misuse your program.**
Be prepared for that.
They will wrap it in scripts, use it on bad internet connections, run many instances of it at once, and use it in environments you haven’t tested in, with quirks you didn’t anticipate.
(Did you know macOS filesystems are case-insensitive but also case-preserving?)

### Future-proofing {#future-proofing}

In software of any kind, it’s crucial that interfaces don’t change without a lengthy and well-documented deprecation process.
Subcommands, arguments, flags, configuration files, environment variables: these are all interfaces, and you’re committing to keeping them working.
([Semantic versioning](https://semver.org/) can only excuse so much change; if you’re putting out a major version bump every month, it’s meaningless.)

**Keep changes additive where you can.**
Rather than modify the behavior of a flag in a backwards-incompatible way, maybe you can add a new flag—as long as it doesn’t bloat the interface too much.
(See also: [Prefer flags to args](#arguments-and-flags).)

**Warn before you make a non-additive change.**
Eventually, you’ll find that you can’t avoid breaking an interface.
Before you do, forewarn your users in the program itself: when they pass the flag you’re looking to deprecate, tell them it’s going to change soon.
Make sure there’s a way they can modify their usage today to make it future-proof, and tell them how to do it.

If possible, you should detect when they’ve changed their usage and not show the warning any more: now they won’t notice a thing when you finally roll out the change.

**Changing output for humans is usually OK.**
The only way to make an interface easy to use is to iterate on it, and if the output is considered an interface, then you can’t iterate on it.
Encourage your users to use `--plain` or `--json` in scripts to keep output stable (see [Output](#output)).

**Don’t have a catch-all subcommand.**
If you have a subcommand that’s likely to be the most-used one, you might be tempted to let people omit it entirely for brevity’s sake.
For example, say you have a `run` command that wraps an arbitrary shell command:

    $ mycmd run echo "hello world"

You could make it so that if the first argument to `mycmd` isn’t the name of an existing subcommand, you assume the user means `run`, so they can just type this:

    $ mycmd echo "hello world"

This has a serious drawback, though: now you can never add a subcommand named `echo`—or _anything at all_—without risking breaking existing usages.
If there’s a script out there that uses `mycmd echo`, it will do something entirely different after that user upgrades to the new version of your tool.

**Don’t allow arbitrary abbreviations of subcommands.**
For example, say your command has an `install` subcommand.
When you added it, you wanted to save users some typing, so you allowed them to type any non-ambiguous prefix, like `mycmd ins`, or even just `mycmd i`, and have it be an alias for `mycmd install`.
Now you’re stuck: you can’t add any more commands beginning with `i`, because there are scripts out there that assume `i` means `install`.

There’s nothing wrong with aliases—saving on typing is good—but they should be explicit and remain stable.

**Don’t create a “time bomb.”**
Imagine it’s 20 years from now.
Will your command still run the same as it does today, or will it stop working because some external dependency on the internet has changed or is no longer maintained?
The server most likely to not exist in 20 years is the one that you are maintaining right now.
(But don’t build in a blocking call to Google Analytics either.)

### Signals and control characters {#signals}

**If a user hits Ctrl-C (the INT signal), exit as soon as possible.**
Say something immediately, before you start clean-up.
Add a timeout to any clean-up code so it can’t hang forever.

**If a user hits Ctrl-C during clean-up operations that might take a long time, skip them.**
Tell the user what will happen when they hit Ctrl-C again, in case it is a destructive action.

For example, when quitting Docker Compose, you can hit Ctrl-C a second time to force your containers to stop immediately instead of shutting them down gracefully.

```
$  docker-compose up
…
^CGracefully stopping... (press Ctrl+C again to force)
```

Your program should expect to be started in a situation where clean-up has not been run.
(See [Crash-only software: More than meets the eye](https://lwn.net/Articles/191059/).)

