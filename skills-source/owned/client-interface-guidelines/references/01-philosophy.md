## Philosophy {#philosophy}

These are what we consider to be the fundamental principles of good CLI design.

### Human-first design {#human-first-design}

Traditionally, UNIX commands were written under the assumption they were going to be used primarily by other programs.
They had more in common with functions in a programming language than with graphical applications.

Today, even though many CLI programs are used primarily (or even exclusively) by humans, a lot of their interaction design still carries the baggage of the past.
It’s time to shed some of this baggage: if a command is going to be used primarily by humans, it should be designed for humans first.

### Simple parts that work&nbsp;together {#simple-parts-that-work-together}

A core tenet of [the original UNIX philosophy](https://en.wikipedia.org/wiki/Unix_philosophy) is the idea that small, simple programs with clean interfaces can be combined to build larger systems.
Rather than stuff more and more features into those programs, you make programs that are modular enough to be recombined as needed.

In the old days, pipes and shell scripts played a crucial role in the process of composing programs together.
Their role might have diminished with the rise of general-purpose interpreted languages, but they certainly haven’t gone away.
What’s more, large-scale automation—in the form of CI/CD, orchestration and configuration management—has flourished.
Making programs composable is just as important as ever.

Fortunately, the long-established conventions of the UNIX environment, designed for this exact purpose, still help us today.
Standard in/out/err, signals, exit codes and other mechanisms ensure that different programs click together nicely.
Plain, line-based text is easy to pipe between commands.
JSON, a much more recent invention, affords us more structure when we need it, and lets us more easily integrate command-line tools with the web.

Whatever software you’re building, you can be absolutely certain that people will use it in ways you didn’t anticipate.
Your software _will_ become a part in a larger system—your only choice is over whether it will be a well-behaved part.

Most importantly, designing for composability does not need to be at odds with designing for humans first.
Much of the advice in this document is about how to achieve both.

### Consistency across programs {#consistency-across-programs}

The terminal’s conventions are hardwired into our fingers.
We had to pay an upfront cost by learning about command line syntax, flags, environment variables and so on, but it pays off in long-term efficiency… as long as programs are consistent.

Where possible, a CLI should follow patterns that already exist.
That’s what makes CLIs intuitive and guessable; that’s what makes users efficient.

That being said, sometimes consistency conflicts with ease of use.
For example, many long-established UNIX commands don't output much information by default, which can cause confusion or worry for people less familiar with the command line.

When following convention would compromise a program’s usability, it might be time to break with it—but such a decision should be made with care.

### Saying (just) enough {#saying-just-enough}

The terminal is a world of pure information.
You could make an argument that information is the interface—and that, just like with any interface, there’s often too much or too little of it.

A command is saying too little when it hangs for several minutes and the user starts to wonder if it’s broken.
A command is saying too much when it dumps pages and pages of debugging output, drowning what’s truly important in an ocean of loose detritus.
The end result is the same: a lack of clarity, leaving the user confused and irritated.

It can be very difficult to get this balance right, but it’s absolutely crucial if software is to empower and serve its users.

### Ease of discovery {#ease-of-discovery}

When it comes to making functionality discoverable, GUIs have the upper hand.
Everything you can do is laid out in front of you on the screen, so you can find what you need without having to learn anything, and perhaps even discover things you didn’t know were possible.

It is assumed that command-line interfaces are the opposite of this—that you have to remember how to do everything.
The original [Macintosh Human Interface Guidelines](https://archive.org/details/applehumaninterf00appl), published in 1987, recommend “See-and-point (instead of remember-and-type),” as if you could only choose one or the other.

These things needn’t be mutually exclusive.
The efficiency of using the command-line comes from remembering commands, but there’s no reason the commands can’t help you learn and remember.

Discoverable CLIs have comprehensive help texts, provide lots of examples, suggest what command to run next, suggest what to do when there is an error.
There are lots of ideas that can be stolen from GUIs to make CLIs easier to learn and use, even for power users.

_Citation: The Design of Everyday Things (Don Norman), Macintosh Human Interface Guidelines_

### Conversation as the&nbsp;norm {#conversation-as-the-norm}

GUI design, particularly in its early days, made heavy use of _metaphor_: desktops, files, folders, recycle bins.
It made a lot of sense, because computers were still trying to bootstrap themselves into legitimacy.
The ease of implementation of metaphors was one of the huge advantages GUIs wielded over CLIs.
Ironically, though, the CLI has embodied an accidental metaphor all along: it’s a conversation.

Beyond the most utterly simple commands, running a program usually involves more than one invocation.
Usually, this is because it’s hard to get it right the first time: the user types a command, gets an error, changes the command, gets a different error, and so on, until it works.
This mode of learning through repeated failure is like a conversation the user is having with the program.

Trial-and-error isn’t the only type of conversational interaction, though.
There are others:

- Running one command to set up a tool and then learning what commands to run to actually start using it.
- Running several commands to set up an operation, and then a final command to run it (e.g. multiple `git add`s, followed by a `git commit`).
- Exploring a system—for example, doing a lot of `cd` and `ls` to get a sense of a directory structure, or `git log` and `git show` to explore the history of a file.
- Doing a dry-run of a complex operation before running it for real.

Acknowledging the conversational nature of command-line interaction means you can bring relevant techniques to bear on its design.
You can suggest possible corrections when user input is invalid, you can make the intermediate state clear when the user is going through a multi-step process, you can confirm for them that everything looks good before they do something scary.

The user is conversing with your software, whether you intended it or not.
At worst, it’s a hostile conversation which makes them feel stupid and resentful.
At best, it’s a pleasant exchange that speeds them on their way with newfound knowledge and a feeling of achievement.

_Further reading: [The Anti-Mac User Interface (Don Gentner and Jakob Nielsen)](https://www.nngroup.com/articles/anti-mac-interface/)_

### Robustness {#robustness-principle}

Robustness is both an objective and a subjective property.
Software should _be_ robust, of course: unexpected input should be handled gracefully, operations should be idempotent where possible, and so on.
But it should also _feel_ robust.

You want your software to feel like it isn’t going to fall apart.
You want it to feel immediate and responsive, as if it were a big mechanical machine, not a flimsy plastic “soft switch.”

Subjective robustness requires attention to detail and thinking hard about what can go wrong.
It’s lots of little things: keeping the user informed about what’s happening, explaining what common errors mean, not printing scary-looking stack traces.

As a general rule, robustness can also come from keeping it simple.
Lots of special cases and complex code tend to make a program fragile.

### Empathy {#empathy}

Command-line tools are a programmer’s creative toolkit, so they should be enjoyable to use.
This doesn’t mean turning them into a video game, or using lots of emoji (though there’s nothing inherently wrong with emoji 😉).
It means giving the user the feeling that you are on their side, that you want them to succeed, that you have thought carefully about their problems and how to solve them.

There’s no list of actions you can take that will ensure they feel this way, although we hope that following our advice will take you some of the way there.
Delighting the user means _exceeding their expectations_ at every turn, and that starts with empathy.

### Chaos {#chaos}

The world of the terminal is a mess.
Inconsistencies are everywhere, slowing us down and making us second-guess ourselves.

Yet it’s undeniable that this chaos has been a source of power.
The terminal, like the UNIX-descended computing environment in general, places very few constraints on what you can build.
In that space, all manner of invention has bloomed.

It’s ironic that this document implores you to follow existing patterns, right alongside advice that contradicts decades of command-line tradition.
We’re just as guilty of breaking the rules as anyone.

The time might come when you, too, have to break the rules.
Do so with intention and clarity of purpose.

> “Abandon a standard when it is demonstrably harmful to productivity or user satisfaction.” — Jef Raskin, [The Humane Interface](https://en.wikipedia.org/wiki/The_Humane_Interface)

