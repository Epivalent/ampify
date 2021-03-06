# No Copyright (-) 2010 The Ampify Authors. This file is under the
# Public Domain license that can be found in the root LICENSE file.

import ampify
import ampify.require

import sys

from optparse import OptionParser
from os import chdir, environ, makedirs, symlink
from os.path import dirname, exists, join, realpath, split

from pyutil.optcomplete import autocomplete, DirCompleter, ListCompleter
from pyutil.env import run_command, CommandNotFound

from ampify.build import ERROR, log, error, exit, lock, unlock
from ampify.build import load_role, install_packages

# ------------------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------------------

AMPIFY_ROOT = dirname(dirname(dirname(realpath(__file__))))
AMPIFY_ROOT_PARENT = dirname(AMPIFY_ROOT)

ERRMSG_GIT_NAME_DETECTION = (
    "ERROR: Couldn't detect the instance name from the Git URL.\n          "
    "Please provide an instance name parameter. Thanks!"
    )

# ------------------------------------------------------------------------------
# Exceptions
# ------------------------------------------------------------------------------

class CompletionResult(Exception):
    def __init__(self, result):
        self.result = result

# ------------------------------------------------------------------------------
# Utility Functions
# ------------------------------------------------------------------------------

def relative_path(source, destination):
    pass

# This function normalises instance names -- just in case someone accidentally
# passed in a path name.
def normalise_instance_name(instance_name):
    instance_name = split(realpath(instance_name))[-1]
    instance_root = join(AMPIFY_ROOT_PARENT, instance_name)
    return instance_name, instance_root

def parse_options(parser, argv, completer=None, exit_if_no_args=False):
    if completer:
        raise CompletionResult(parser)
    if (argv == ['--help']) or (argv == ['-h']):
        parser.print_help()
        sys.exit(1)
    options, args = parser.parse_args(argv)
    if exit_if_no_args and not args:
        parser.print_help()
        sys.exit(1)
    return options, args

# ------------------------------------------------------------------------------
# Main Runner
# ------------------------------------------------------------------------------

def main(argv=None, show_help=False):

    argv = argv or sys.argv[1:]

    # Set the script name to ``amp`` so that OptionParser error messages don't
    # display a meaningless ``main.py`` to end users.
    sys.argv[0] = 'amp'

    usage = ("""Usage: amp <command> [options]
    \nCommands:
    \n%s
    version  show the version number and exit
    \nSee `amp help <command>` for more info on a specific command.""" %
    '\n'.join("    %-8s %s" % (cmd, COMMANDS[cmd].help) for cmd in sorted(COMMANDS))
    )

    autocomplete(
        OptionParser(add_help_option=False),
        ListCompleter(AUTOCOMPLETE_COMMANDS.keys()),
        subcommands=AUTOCOMPLETE_COMMANDS
        )

    if not argv:
        show_help = True
    else:
        command = argv[0]
        argv = argv[1:]
        if command in ['-h', '--help']:
            show_help = True
        elif command == 'help':
            if argv:
                command = argv[0]
                argv = ['--help']
            else:
                show_help = True
        if command in ['-v', '--version', 'version']:
            print('amp version %s' % ampify.__release__)
            sys.exit()

    if show_help:
        print(usage)
        sys.exit(1)

    if command in COMMANDS:
        return COMMANDS[command](argv)

    # We support git-command like behaviour. That is, if there's an external
    # binary named ``amp-foo`` available on the ``$PATH``, then running ``amp
    # foo`` will automatically delegate to it.
    try:
        output, retcode = run_command(
            ['amp-%s' % command] + argv, retcode=True, redirect_stdout=False,
            redirect_stderr=False
            )
    except CommandNotFound:
        exit("ERROR: Unknown command %r" % command)

    if retcode:
        sys.exit(retcode)

# ------------------------------------------------------------------------------
# Build Command
# ------------------------------------------------------------------------------

def build(argv=None, completer=None):

    op = OptionParser(usage="Usage: amp build [options]", add_help_option=False)

    op.add_option('--role', dest='role', default='default',
                  help="specify a non-default role to build")

    options, args = parse_options(op, argv, completer)

    load_role(options.role)
    install_packages()

# ------------------------------------------------------------------------------
# Deploy Command
# ------------------------------------------------------------------------------

def deploy(argv=None, completer=None):

    op = OptionParser(
        usage="Usage: amp deploy <instance-name> [options]",
        add_help_option=False
        )

    op.add_option('--test', dest='test', action='store_true', default=False,
                  help="run tests before completing the switch")

    options, args = parse_options(op, argv, completer, True)

# ------------------------------------------------------------------------------
# Hub Command
# ------------------------------------------------------------------------------

def hub(argv=None, completer=None):

    op = OptionParser(
        usage="Usage: amp hub [register|update] [options]",
        add_help_option=False
        )

    options, args = parse_options(op, argv, completer, True)

# ------------------------------------------------------------------------------
# Init Command
# ------------------------------------------------------------------------------

def init(argv=None, completer=None):

    op = OptionParser(
        usage="Usage: amp init <instance-name> [options]",
        add_help_option=False
        )

    op.add_option('--clobber', dest='clobber', action='store_true',
                  help="clobber any existing files/directories if they exist")

    op.add_option('--from', dest='git_repo', default='',
                  help="initialise by cloning the given git repository")

    options, args = parse_options(op, argv, completer)

    git_repo = options.git_repo
    if git_repo:
        if args:
            instance_name = args[0]
        else:
            instance_name = git_repo.split('/')[-1].rsplit('.', 1)[0]
            if not instance_name:
                exit(ERRMSG_GIT_NAME_DETECTION)
    else:
        if args:
            instance_name = args[0]
        else:
            op.print_help()
            sys.exit(1)

    instance_name, instance_root = normalise_instance_name(instance_name)
    clobber = options.clobber

    if exists(instance_root):
        if not clobber:
            exit(
                "ERROR: A directory already exists at %s\n          "
                "Use the --clobber parameter to overwrite the directory"
                % instance_root
                )
        chdir(instance_root)
        diff = do('git', 'diff', '--cached', '--name-only', redirect_stdout=1)
        if diff.strip():
            error(
                "ERROR: You have a dirty working tree at %s\n          "
                "Please either commit your changes or move your files.\n"
                % instance_root
                )
            error("  These are the problematic files:")
            for filename in diff.strip().splitlines():
                log("    %s" % filename, ERROR)
            print
        first_run = 0
    else:
        create = query("Create a instance at %s" % instance_root).lower()
        if not create.startswith('y'):
            sys.exit(2)
        makedirs(instance_root)
        print
        print("Created %s" % instance_root)
        print
        chdir(instance_root)
        do('git', 'init')
        print
        readme = open('README.md', 'wb')
        readme.close()
        do('git', 'add', 'README.md')
        do('git', 'commit', '-m', "Initialised the instance [amp].")
        first_run = 1

    diff = do('git', 'diff', '--cached', '--name-only', redirect_stdout=1)
    if diff.strip():
        do('git', 'commit', '-m', "Updated instance [amp].")

    print(DEBUG)

# ------------------------------------------------------------------------------
# Run Command
# ------------------------------------------------------------------------------

def run(argv=None, completer=None, debug=False):
    
    op = OptionParser(
        usage="Usage: amp run <instance-name> [options] [stop|quit|restart]",
        add_help_option=False
        )

    op.add_option('-d', '--debug', dest='debug', action='store_true',
                  help="enable debug mode")

    op.add_option("--file", dest="filename",
                  help="Input file to read data from")

    if completer:
        return op, DirCompleter(AMPIFY_ROOT_PARENT)

    options, args = parse_options(op, argv, completer, True)

    if options.debug:
        debug = True

    instance_name, instance_root = normalise_instance_name(args[0])

# ------------------------------------------------------------------------------
# Test Command
# ------------------------------------------------------------------------------

def test(argv=None, completer=None, run_all=False):

    op = OptionParser(usage="Usage: amp test [options]", add_help_option=False)

    op.add_option('-a', '--all', dest='all', action='store_true',
                  help="run the comprehensive test suite")

    options, args = parse_options(op, argv, completer)

    if options.all:
        run_all = True

    print("Running tests...")

# ------------------------------------------------------------------------------
# Help Strings
# ------------------------------------------------------------------------------

# These, along with other strings, should perhaps be internationalised at a
# later date.
build.help = "download and build the ampify zero dependencies"
deploy.help = "deploy an instance to remote host(s)"
hub.help = "interact with amphub"
init.help = "initialise a new amp instance"
run.help = "run the components for an amp instance"
test.help = "run the ampify zero test suite"

# ------------------------------------------------------------------------------
# Command Mapping
# ------------------------------------------------------------------------------

COMMANDS = {
    'build': build,
    'deploy': deploy,
    'hub': hub,
    'init': init,
    'run': run,
    'test': test
    }

# ------------------------------------------------------------------------------
# Command Autocompletion
# ------------------------------------------------------------------------------

AUTOCOMPLETE_COMMANDS = COMMANDS.copy()

AUTOCOMPLETE_COMMANDS['help'] = lambda completer: (
    OptionParser(add_help_option=False),
    ListCompleter(COMMANDS.keys())
    )

AUTOCOMPLETE_COMMANDS['version'] = lambda completer: (
    OptionParser(add_help_option=False),
    DirCompleter(AMPIFY_ROOT_PARENT)
    )

def make_autocompleter(command):
    def wrapper(completer):
        try:
            parser = command(completer=completer)
        except CompletionResult:
            parser = sys.exc_info()[1].result
        if isinstance(parser, tuple):
            parser, completer = parser
        return autocomplete(parser, completer)
    return wrapper

for command in AUTOCOMPLETE_COMMANDS.values():
    command.autocomplete = make_autocompleter(command)

# ------------------------------------------------------------------------------
# Script Runner
# ------------------------------------------------------------------------------

if __name__ == '__main__':
    main()
