### Arguments and flags {#arguments-and-flags}

A note on terminology:

- _Arguments_, or _args_, are positional parameters to a command.
  For example, the file paths you provide to `cp` are args.
  The order of args is often important: `cp foo bar` means something different from `cp bar foo`.
- _Flags_ are named parameters, denoted with either a hyphen and a single-letter name (`-r`) or a double hyphen and a multiple-letter name (`--recursive`).
  They may or may not also include a user-specified value (`--file foo.txt`, or `--file=foo.txt`).
  The order of flags, generally speaking, does not affect program semantics.

**Prefer flags to args.**
It’s a bit more typing, but it makes it much clearer what is going on.
It also makes it easier to make changes to how you accept input in the future.
Sometimes when using args, it’s impossible to add new input without breaking existing behavior or creating ambiguity.

_Citation: [12 Factor CLI Apps](https://medium.com/@jdxcode/12-factor-cli-apps-dd3c227a0e46)._

**Have full-length versions of all flags.**
For example, have both `-h` and `--help`.
Having the full version is useful in scripts where you want to be verbose and descriptive, and you don’t have to look up the meaning of flags everywhere.

_Citation: [GNU Coding Standards](https://www.gnu.org/prep/standards/html_node/Command_002dLine-Interfaces.html)._

**Only use one-letter flags for commonly used flags,** particularly at the top-level when using subcommands.
That way you don’t “pollute” your namespace of short flags, forcing you to use convoluted letters and cases for flags you add in the future.

**Multiple arguments are fine for simple actions against multiple files.**
For example, `rm file1.txt file2.txt file3.txt`.
This also makes it work with globbing: `rm *.txt`.

**If you’ve got two or more arguments for different things, you’re probably doing something wrong.**
The exception is a common, primary action, where the brevity is worth memorizing.
For example, `cp <source> <destination>`.

_Citation: [12 Factor CLI Apps](https://medium.com/@jdxcode/12-factor-cli-apps-dd3c227a0e46)._

**Use standard names for flags, if there is a standard.**
If another commonly used command uses a flag name, it’s best to follow that existing pattern.
That way, a user doesn’t have to remember two different options (and which command it applies to), and users can even guess an option without having to look at the help text.

Here's a list of commonly used options:

- `-a`, `--all`: All.
  For example, `ps`, `fetchmail`.
- `-d`, `--debug`: Show debugging output.
- `-f`, `--force`: Force.
  For example, `rm -f` will force the removal of files, even if it thinks it does not have permission to do it.
  This is also useful for commands which are doing something destructive that usually require user confirmation, but you want to force it to do that destructive action in a script.
- `--json`: Display JSON output.
  See the [output](#output) section.
- `-h`, `--help`: Help.
  This should only mean help.
  See the [help](#help) section.
- `-n`, `--dry-run`: Dry run. 
  Do not run the command, but describe the changes that would occur if the command were run. For example, `rsync`, `git add`.
- `--no-input`: See the [interactivity](#interactivity) section.
- `-o`, `--output`: Output file.
  For example, `sort`, `gcc`.
- `-p`, `--port`: Port.
  For example, `psql`, `ssh`.
- `-q`, `--quiet`: Quiet.
  Display less output.
  This is particularly useful when displaying output for humans that you might want to hide when running in a script.
- `-u`, `--user`: User.
  For example, `ps`, `ssh`.
- `--version`: Version.
- `-v`: This can often mean either verbose or version.
  You might want to use `-d` for verbose and this for version, or for nothing to avoid confusion.

**Make the default the right thing for most users.**
Making things configurable is good, but most users are not going to find the right flag and remember to use it all the time (or alias it).
If it’s not the default, you’re making the experience worse for most of your users.

For example, `ls` has terse default output to optimize for scripts and other historical reasons, but if it were designed today, it would probably default to `ls -lhF`.

**Prompt for user input.**
If a user doesn’t pass an argument or flag, prompt for it.
(See also: [Interactivity](#interactivity))

**Never _require_ a prompt.**
Always provide a way of passing input with flags or arguments.
If `stdin` is not an interactive terminal, skip prompting and just require those flags/args.

**Confirm before doing anything dangerous.**
A common convention is to prompt for the user to type `y` or `yes` if running interactively, or requiring them to pass `-f` or `--force` otherwise.

“Dangerous” is a subjective term, and there are differing levels of danger:

- **Mild:** A small, local change such as deleting a file.
  You might want to prompt for confirmation, you might not.
  For example, if the user is explicitly running a command called something like “delete,” you probably don’t need to ask.
- **Moderate:** A bigger local change like deleting a directory, a remote change like deleting a resource of some kind, or a complex bulk modification that can’t be easily undone.
  You usually want to prompt for confirmation here.
  Consider giving the user a way to “dry run” the operation so they can see what’ll happen before they commit to it.
- **Severe:** Deleting something complex, like an entire remote application or server.
  You don’t just want to prompt for confirmation here—you want to make it hard to confirm by accident.
  Consider asking them to type something non-trivial such as the name of the thing they’re deleting.
  Let them alternatively pass a flag such as `--confirm="name-of-thing"`, so it’s still scriptable.

Consider whether there are non-obvious ways to accidentally destroy things.
For example, imagine a situation where changing a number in a configuration file from 10 to 1 means that 9 things will be implicitly deleted—this should be considered a severe risk, and should be difficult to do by accident.

**If input or output is a file, support `-` to read from `stdin` or write to `stdout`.**
This lets the output of another command be the input of your command and vice versa, without using a temporary file.
For example, `tar` can extract files from `stdin`:

```
$ curl https://example.com/something.tar.gz | tar xvf -
```

**If a flag can accept an optional value, allow a special word like “none”.**
For example, `ssh -F` takes an optional filename of an alternative `ssh_config` file, and `ssh -F none` runs SSH with no config file. Don’t just use a blank value—this can make it ambiguous whether arguments are flag values or arguments.

**If possible, make arguments, flags and subcommands order-independent.**
A lot of CLIs, especially those with subcommands, have unspoken rules on where you can put various arguments.
For example a command might have a `--foo` flag that only works if you put it before the subcommand:

```
$ mycmd --foo=1 subcmd
works

$ mycmd subcmd --foo=1
unknown flag: --foo
```

This can be very confusing for the user—especially given that one of the most common things users do when trying to get a command to work is to hit the up arrow to get the last invocation, stick another option on the end, and run it again.
If possible, try to make both forms equivalent, although you might run up against the limitations of your argument parser.

**Do not read secrets directly from flags.**
When a command accepts a secret, e.g. via a `--password` flag,
the flag value will leak the secret into `ps` output and potentially shell history.
And, this sort of flag encourages the use of insecure environment variables for secrets.
(Environment variables are insecure because they can often be read by other users, their values end up in debug logs, etc.)

Consider accepting sensitive data only via files, e.g. with a `--password-file` flag, or via `stdin`.
A `--password-file` flag allows a secret to be passed in discreetly, in a wide variety of contexts.

(It’s possible to pass a file’s contents into a flag in Bash by using `--password $(< password.txt)`.
This approach has the same security problems mentioned above.
It’s best avoided.)

### Interactivity {#interactivity}

**Only use prompts or interactive elements if `stdin` is an interactive terminal (a TTY).**
This is a pretty reliable way to tell whether you’re piping data into a command or whether it's being run in a script, in which case a prompt won’t work and you should throw an error telling the user what flag to pass.

**If `--no-input` is passed, don’t prompt or do anything interactive.**
This allows users an explicit way to disable all prompts in commands.
If the command requires input, fail and tell the user how to pass the information as a flag.

**If you’re prompting for a password, don’t print it as the user types.**
This is done by turning off echo in the terminal.
Your language should have helpers for this.

**Let the user escape.**
Make it clear how to get out.
(Don’t do what vim does.)
If your program hangs on network I/O etc, always make Ctrl-C still work.
If it’s a wrapper around program execution where Ctrl-C can’t quit (SSH, tmux, telnet, etc), make it clear how to do that.
For example, SSH allows escape sequences with the `~` escape character.

### Subcommands

If you’ve got a tool that’s sufficiently complex, you can reduce its complexity by making a set of subcommands.
If you have several tools that are very closely related, you can make them easier to use and discover by combining them into a single command (for example, RCS vs. Git).

They’re useful for sharing stuff—global flags, help text, configuration, storage mechanisms.

**Be consistent across subcommands.**
Use the same flag names for the same things, have similar output formatting, etc. 

**Use consistent names for multiple levels of subcommand.**
If a complex piece of software has lots of objects and operations that can be performed on those objects, it is a common pattern to use two levels of subcommand for this, where one is a noun and one is a verb.
For example, `docker container create`.
Be consistent with the verbs you use across different types of objects.

Either `noun verb` or `verb noun` ordering works, but `noun verb` seems to be more common.

_Further reading: [User experience, CLIs, and breaking the world, by John Starich](https://uxdesign.cc/user-experience-clis-and-breaking-the-world-baed8709244f)._

**Don’t have ambiguous or similarly-named commands.**
For example, having two subcommands called “update” and “upgrade” is quite confusing.
You might want to use different words, or disambiguate with extra words.

