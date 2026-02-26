### The Basics

There are a few basic rules you need to follow.
Get these wrong, and your program will be either very hard to use, or flat-out broken.

**Use a command-line argument parsing library where you can.**
Either your language’s built-in one, or a good third-party one.
They will normally handle arguments, flag parsing, help text, and even spelling suggestions in a sensible way.

Here are some that we like:
* Multi-platform: docopt
* Bash: argbash
* Go: Cobra, cli
* Haskell: optparse-applicative
* Java: picocli
* Julia: ArgParse.jl, Comonicon.jl
* Kotlin: clikt
* Node: oclif
* Deno: parseArgs
* Perl: Getopt::Long
* PHP: console, CLImate
* Python: Argparse, Click, Typer
* Ruby: TTY
* Rust: clap
* Swift: swift-argument-parser

**Return zero exit code on success, non-zero on failure.**
Exit codes are how scripts determine whether a program succeeded or failed, so you should report this correctly.
Map the non-zero exit codes to the most important failure modes.

**Send output to `stdout`.**
The primary output for your command should go to `stdout`.
Anything that is machine readable should also go to `stdout`—this is where piping sends things by default.

**Send messaging to `stderr`.**
Log messages, errors, and so on should all be sent to `stderr`.
This means that when commands are piped together, these messages are displayed to the user and not fed into the next command.

### Help

**Display extensive help text when asked.**
Display help when passed `-h` or `--help` flags.
This also applies to subcommands which might have their own help text.

**Display concise help text by default.**
When `myapp` or `myapp subcommand` requires arguments to function,
and is run with no arguments,
display concise help text.

You can ignore this guideline
if your program is interactive by default (e.g. `npm init`).

The concise help text should only include:

- A description of what your program does.
- One or two example invocations.
- Descriptions of flags, unless there are lots of them.
- An instruction to pass the `--help` flag for more information.

`jq` does this well.
When you type `jq`, it displays an introductory description and an example, then prompts you to pass `jq --help` for the full listing of flags:

```
$ jq
jq - commandline JSON processor [version 1.6]

Usage:    jq [options] <jq filter> [file...]
    jq [options] --args <jq filter> [strings...]
    jq [options] --jsonargs <jq filter> [JSON_TEXTS...]

jq is a tool for processing JSON inputs, applying the given filter to
its JSON text inputs and producing the filter's results as JSON on
standard output.

The simplest filter is ., which copies jq's input to its output
unmodified (except for formatting, but note that IEEE754 is used
for number representation internally, with all that that implies).

For more advanced filters see the jq(1) manpage ("man jq")
and/or jq documentation
Example:

    $ echo '{"foo": 0}' | jq .
    {
        "foo": 0
    }

For a listing of options, use jq --help.
```

**Show full help when `-h` and `--help` are passed.**
All of these should show help:

```
$ myapp
$ myapp --help
$ myapp -h
```

Ignore any other flags and arguments that are passed—you should be able to add `-h` to the end of anything and it should show help.
Don’t overload `-h`.

If your program is `git`-like, the following should also offer help:

```
$ myapp help
$ myapp help subcommand
$ myapp subcommand --help
$ myapp subcommand -h
```

**Provide a support path for feedback and issues.**
A website or GitHub link in the top-level help text is common.

**In help text, link to the web version of the documentation.**
If you have a specific page or anchor for a subcommand, link directly to that.
This is particularly useful if there is more detailed documentation on the web, or further reading that might explain the behavior of something.

**Lead with examples.**
Users tend to use examples over other forms of documentation, so show them first in the help page, particularly the common complex uses.
If it helps explain what it’s doing and it isn’t too long, show the actual output too.

You can tell a story with a series of examples, building your way toward complex uses.
**If you’ve got loads of examples, put them somewhere else,** in a cheat sheet command or a web page.
It’s useful to have exhaustive, advanced examples, but you don’t want to make your help text really long.

For more complex use cases, e.g. when integrating with another tool, it might be appropriate to write a fully-fledged tutorial.

**Display the most common flags and commands at the start of the help text.**
It’s fine to have lots of flags, but if you’ve got some really common ones, display them first.
For example, the Git command displays the commands for getting started and the most commonly used subcommands first:

```
$ git
usage: git [--version] [--help] [-C <path>] [-c <name>=<value>]
           [--exec-path[=<path>]] [--html-path] [--man-path] [--info-path]
           [-p | --paginate | -P | --no-pager] [--no-replace-objects] [--bare]
           [--git-dir=<path>] [--work-tree=<path>] [--namespace=<name>]
           <command> [<args>]

These are common Git commands used in various situations:

start a working area (see also: git help tutorial)
   clone      Clone a repository into a new directory
   init       Create an empty Git repository or reinitialize an existing one

work on the current change (see also: git help everyday)
   add        Add file contents to the index
   mv         Move or rename a file, a directory, or a symlink
   reset      Reset current HEAD to the specified state
   rm         Remove files from the working tree and from the index

examine the history and state (see also: git help revisions)
   bisect     Use binary search to find the commit that introduced a bug
   grep       Print lines matching a pattern
   log        Show commit logs
   show       Show various types of objects
   status     Show the working tree status
…
```

**Use formatting in your help text.**
Bold headings make it much easier to scan.
But, try to do it in a terminal-independent way so that your users aren't staring down a wall of escape characters.

```
$ heroku apps --help
list your apps

USAGE
  $ heroku apps

OPTIONS
  -A, --all          include apps in all teams
  -p, --personal     list apps in personal account when a default team is set
  -s, --space=space  filter by space
  -t, --team=team    team to use
  --json             output in json format

EXAMPLES
  $ heroku apps
  === My Apps
  example
  example2

  === Collaborated Apps
  theirapp   other@owner.name

COMMANDS
  apps:create     creates a new app
  apps:destroy    permanently destroy an app
  apps:errors     view app errors
  apps:favorites  list favorited apps
  apps:info       show detailed app information
  apps:join       add yourself to a team app
  apps:leave      remove yourself from a team app
  apps:lock       prevent team members from joining an app
  apps:open       open the app in a web browser
  apps:rename     rename an app
  apps:stacks     show the list of available stacks
  apps:transfer   transfer applications to another user or team
  apps:unlock     unlock an app so any team member can join
```

Note: When `heroku apps --help` is piped through a pager, the command emits no escape characters.

**If the user did something wrong and you can guess what they meant, suggest it.**
For example, `brew update jq` tells you that you should run `brew upgrade jq`.

You can ask if they want to run the suggested command, but don’t force it on them.
For example:

```
$ heroku pss
 ›   Warning: pss is not a heroku command.
Did you mean ps? [y/n]:
```

Rather than suggesting the corrected syntax, you might be tempted to just run it for them, as if they’d typed it right in the first place.
Sometimes this is the right thing to do, but not always.

Firstly, invalid input doesn’t necessarily imply a simple typo—it can often mean the user has made a logical mistake, or misused a shell variable.
Assuming what they meant can be dangerous, especially if the resulting action modifies state.

Secondly, be aware that if you change what the user typed, they won’t learn the correct syntax.
In effect, you’re ruling that the way they typed it is valid and correct, and you’re committing to supporting that indefinitely.
Be intentional in making that decision, and document both syntaxes.

**If your command is expecting to have something piped to it and `stdin` is an interactive terminal, display help immediately and quit.**
This means it doesn’t just hang, like `cat`.
Alternatively, you could print a log message to `stderr`.

### Documentation

The purpose of help text is to give a brief, immediate sense of what your tool is, what options are available, and how to perform the most common tasks.
Documentation, on the other hand, is where you go into full detail.
It’s where people go to understand what your tool is for, what it _isn’t_ for, how it works and how to do everything they might need to do.

**Provide web-based documentation.**
People need to be able to search online for your tool’s documentation, and to link other people to specific parts.
The web is the most inclusive documentation format available.

**Provide terminal-based documentation.**
Documentation in the terminal has several nice properties: it’s fast to access, it stays in sync with the specific installed version of the tool, and it works without an internet connection.

**Consider providing man pages.**
man pages, Unix’s original system of documentation, are still in use today, and many users will reflexively check `man mycmd` as a first step when trying to learn about your tool.
To make them easier to generate, you can use a tool like ronn (which can also generate your web docs).

However, not everyone knows about `man`, and it doesn’t run on all platforms, so you should also make sure your terminal docs are accessible via your tool itself.
For example, `git` and `npm` make their man pages accessible via the `help` subcommand, so `npm help ls` is equivalent to `man npm-ls`.

```
NPM-LS(1)                                                            NPM-LS(1)

NAME
       npm-ls - List installed packages

SYNOPSIS
         npm ls [[<@scope>/]<pkg> ...]

         aliases: list, la, ll

DESCRIPTION
       This command will print to stdout all the versions of packages that are
       installed, as well as their dependencies, in a tree-structure.

       ...
```
