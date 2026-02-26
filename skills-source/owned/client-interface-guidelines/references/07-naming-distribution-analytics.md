### Naming {#naming}

> “Note the obsessive use of abbreviations and avoidance of capital letters; [Unix] is a system invented by people to whom repetitive stress disorder is what black lung is to miners.
> Long names get worn down to three-letter nubbins, like stones smoothed by a river.”
> — Neal Stephenson, _[In the Beginning was the Command Line](https://web.stanford.edu/class/cs81n/command.txt)_

The name of your program is particularly important on the CLI: your users will be typing it all the time, and it needs to be easy to remember and type.

**Make it a simple, memorable word.**
But not too generic, or you’ll step on the toes of other commands and confuse users.
For example, both ImageMagick and Windows used the command `convert`.

**Use only lowercase letters, and dashes if you really need to.**
`curl` is a good name, `DownloadURL` is not.

**Keep it short.**
Users will be typing it all the time.
Don’t make it _too_ short: the very shortest commands are best reserved for the common utilities used all the time, such as `cd`, `ls`, `ps`.

**Make it easy to type.**
If you expect people to type your command name all day, make it easy on their hands.

A real-world example: long before Docker Compose was `docker compose`, it was [`plum`](https://github.com/aanand/fig/blob/0eb7d308615bae1ad4be1ca5112ac7b6b6cbfbaf/setup.py#L26).
This turned out to be such an awkward, one-handed hopscotch that it was immediately renamed to [`fig`](https://github.com/aanand/fig/commit/0cafdc9c6c19dab2ef2795979dc8b2f48f623379), which – as well as being shorter – flows much more easily.

_Further reading: [The Poetics of CLI Command Names](https://smallstep.com/blog/the-poetics-of-cli-command-names/)_

### Distribution {#distribution}

**If possible, distribute as a single binary.**
If your language doesn’t compile to binary executables as standard, see if it has something like [PyInstaller](https://www.pyinstaller.org/).
If you really can’t distribute as a single binary, use the platform’s native package installer so you aren’t scattering things on disk that can’t easily be removed.
Tread lightly on the user’s computer.

If you’re making a language-specific tool, such as a code linter, then this rule doesn’t apply—it’s safe to assume the user has an interpreter for that language installed on their computer.

**Make it easy to uninstall.**
If it needs instructions, put them at the bottom of the install instructions—one of the most common times people want to uninstall software is right after installing it.

### Analytics {#analytics}

Usage metrics can be helpful to understand how users are using your program, how to make it better, and where to focus effort.
But, unlike websites, users of the command-line expect to be in control of their environment, and it is surprising when programs do things in the background without telling them.

**Do not phone home usage or crash data without consent.**
Users will find out, and they will be angry.
Be very explicit about what you collect, why you collect it, how anonymous it is and how you go about anonymizing it, and how long you retain it for.

Ideally, ask users whether they want to contribute data (“opt-in”).
If you choose to do it by default (“opt-out”), then clearly tell users about it on your website or first run, and make it easy to disable.

Examples of projects that collect usage statistics:

- Angular.js [collects detailed analytics using Google Analytics](https://angular.io/analytics), in the name of feature prioritization.
  You have to explicitly opt in.
  You can change the tracking ID to point to your own Google Analytics property if you want to track Angular usage inside your organization.
- Homebrew sends metrics to Google Analytics and has [a nice FAQ](https://docs.brew.sh/Analytics) detailing their practices.
- Next.js [collects anonymized usage statistics](https://nextjs.org/telemetry) and is enabled by default.

**Consider alternatives to collecting analytics.**

- Instrument your web docs.
  If you want to know how people are using your CLI tool, make a set of docs around the use cases you’d like to understand best, and see how they perform over time.
  Look at what people search for within your docs.
- Instrument your downloads.
  This can be a rough metric to understand usage and what operating systems your users are running.
- Talk to your users.
  Reach out and ask people how they’re using your tool.
  Encourage feedback and feature requests in your docs and repos, and try to draw out more context from those who submit feedback.

_Further reading: [Open Source Metrics](https://opensource.guide/metrics/)_

