# -*- coding: utf-8 -*-

import logging
import os
import shutil
import sys

import click

from cekit.config import default_work_dir
from cekit.config import Config
from cekit.errors import CekitError
from cekit.log import setup_logging
from cekit.tools import Map
from cekit.version import __version__

LOGGER = logging.getLogger('cekit')
CONFIG = Config()


@click.group(context_settings=dict(max_content_width=100))
@click.option('--descriptor', metavar="PATH", help="Path to image descriptor file.", default="image.yaml", show_default=True)
@click.option('-v', '--verbose', help="Enable verbose output.", is_flag=True)
@click.option('--nocolor', help="Disable color output.", is_flag=True)
@click.option('--work-dir', metavar="PATH", help="Location of the working directory.", default=default_work_dir, show_default=True)
@click.option('--config', metavar="PATH", help="Path to configuration file.", default=default_work_dir + "/config", show_default=True)
@click.option('--redhat', help="Set default options for Red Hat internal infrastructure.", is_flag=True)
@click.option('--target', metavar="PATH", help="Path to directory where files should be generated", default="target", show_default=True)
@click.version_option(message="%(version)s", version=__version__)
def cli(descriptor, verbose, nocolor, work_dir, config, redhat, target):  # pylint: disable=unused-argument,too-many-arguments
    """
    ABOUT

        CEKit -- Container Evolution Kit

        CEKit helps building container images from image definition files with strong focus on modularity and code reuse.

    LINKS

    \b
        Website: https://cekit.io/
        Documentation: https://docs.cekit.io/
        Issue tracker: https://github.com/cekit/cekit/issues

    EXAMPLES

        Build container image in Docker

            $ cekit build docker

        Execute tests for the example/app:1.0 image

            $ cekit test example/app:1.0
    """


@cli.group(short_help="Build container image")
@click.option('--validate', help="Do not execute the build nor generate files, just validate image and module descriptors.", is_flag=True)
@click.option('--dry-run', help="Do not execute the build, just generate required files.", is_flag=True)
@click.option('--overrides', metavar="JSON", help="Inline overrides in JSON format.", multiple=True)
@click.option('--overrides-file', 'overrides', metavar="PATH", help="Path to overrides file in YAML format.", multiple=True)
def build(validate, dry_run, overrides):  # pylint: disable=unused-argument
    """
    DESCRIPTION

        Executes container image build using selected builder.

    BUILDERS

        Currently supported builders: Docker, OSBS, Podman and Buildah.

            $ cekit build BUILDER

        Run 'cekit build BUILDER --help' for more information about particular builder.

    OVERRIDES

        You can specify overrides to modify the container image build. You can read more about overrides in the documentation: https://docs.cekit.io/en/latest/overrides.html.

        Overrides can be specified inline (--overrides) or as a path to file (--overrides-file).

        Overrides can be specified multiple times.

        Please note that order matters; overrides on the right hand side take precedence! For example:

            $ cekit build --overrides '{"from": "custom/image:1.0"}' --overrides '{"from": "custom/image:2.0"}'

        Will change the 'from' key in the descriptor to 'custom/image:2.0'.
    """


@build.command(name="docker", short_help="Build using Docker engine")
@click.option('--pull', help="Always try to fetch latest base image.", is_flag=True)
@click.option('--no-squash', help="Do not squash the image after build is done.", is_flag=True)
@click.option('--tag', 'tags', metavar="TAG", help="Use specified tag to tag the image after build, can be specified multiple times.", multiple=True)
@click.pass_context
def build_docker(ctx, pull, no_squash, tags):  # pylint: disable=unused-argument
    """
    DESCRIPTION

        Executes container image build locally using Docker builder.

        https://docs.docker.com/

        By default after image is built, it is squashed using the https://github.com/goldmann/docker-squash tool. You can disable it by specifying the '--no-squash' parameter.
    """
    run_build(ctx, 'docker')


@build.command(name="buildah", short_help="Build using Buildah engine")
@click.option('--pull', help="Always try to fetch latest base image.", is_flag=True)
@click.option('--no-squash', help="Do not squash the image after build is done.", is_flag=True)
@click.option('--tag', 'tags', metavar="TAG", help="Use specified tag to tag the image after build, can be specified multiple times.", multiple=True)
@click.pass_context
def build_buildah(ctx, pull, no_squash, tags):  # pylint: disable=unused-argument
    """
    DESCRIPTION

        Executes container image build locally using Buildah builder.

        https://buildah.io/
    """
    run_build(ctx, 'buildah')


@build.command(name="podman", short_help="Build using Podman engine")
@click.option('--pull', help="Always try to fetch latest base image.", is_flag=True)
@click.option('--no-squash', help="Do not squash the image after build is done.", is_flag=True)
@click.option('--tag', 'tags', metavar="TAG", help="Use specified tag to tag the image after build, can be specified multiple times.", multiple=True)
@click.pass_context
def build_podman(ctx, pull, no_squash, tags):  # pylint: disable=unused-argument
    """
    DESCRIPTION

        Executes container image build locally using Podman builder.

        https://podman.io/
    """
    run_build(ctx, 'podman')


@build.command(name="osbs", short_help="Build using OSBS engine")
@click.option('--release', help="Execute a release build.", is_flag=True)
@click.option('--user', metavar="USER", help="User used to kick the build as.")
@click.option('--nowait', help="Do not wait for the task to finish.", is_flag=True)
@click.option('--stage', help="Use stage environmen.", is_flag=True)
@click.option('--sync-only', help="Generate files and sync with dist-git, but do not execute build.", is_flag=True)
@click.option('--commit-message', metavar="MESSAGE", help="Custom dist-git commit message.")
@click.option('--assume-yes', '-y', help="Execute build in non-interactive mode.", is_flag=True)
@click.pass_context
def build_osbs(ctx, release, user, nowait, stage, sync_only, commit_message, assume_yes):  # pylint: disable=unused-argument
    """
    DESCRIPTION

        Executes container image build using OSBS builder.

        https://osbs.readthedocs.io

    EXAMPLES

        Execute scratch build in OSBS

            $ cekit build osbs

        Execute regular (release) build in OSBS

            $ cekit build osbs --release

        Execute regular (release) build in OSBS with a custom commit message in dist-git

            $ cekit build osbs --release --commit-message "Release 1.0"
    """
    run_build(ctx, 'osbs')


@cli.group(short_help="Execute container image tests")
@click.option('--image', help="Image to run tests against.")
@click.option('--overrides', metavar="JSON", help="Inline overrides in JSON format.", multiple=True)
@click.option('--overrides-file', 'overrides', metavar="PATH", help="Path to overrides file in YAML format.", multiple=True)
def test(image, overrides):  # pylint: disable=unused-argument
    """
    DESCRIPTION

        Executes container image tests using selected framework.

    TEST FRAMEWORKS

        We currently support only Behave.

            $ cekit test behave

        Run 'cekit test behave --help' for more information about this particular tester.
    """


@test.command(name="behave", short_help="Run Behave tests")
@click.option('--steps-url', help="Behave steps library.", default='https://github.com/cekit/behave-test-steps.git', show_default=True)
@click.option('--wip', help="Run test scenarios tagged with @wip only.", is_flag=True)
@click.option('--name', 'names', help="Run test scenario with the specified name, can be used specified times.", multiple=True)
@click.pass_context
def test_behave(ctx, steps_url, wip, names):  # pylint: disable=unused-argument
    """
    DESCRIPTION

        Execute Behave container image tests locally using Docker

        NOTE: Image to test must be available in the Docker daemon. It won't be pulled automatically!

    EXAMPLES

        Execute tests for the example/app:1.0 image

            $ cekit test --image example/app:1.0 behave

        Execute tests that are currently developed and marked with @wip

            $ cekit test --image example/app:1.0 behave --wip

        Execute specific scenario

            $ cekit test --image example/app:1.0 behave --name 'Check that product labels are correctly set'
    """

    if wip and names:
        raise click.UsageError("Parameters --name and --wip cannot be used together")

    run_test(ctx, 'behave')


def prepare_params(ctx, params=None):

    if params is None:
        params = Map({})

    if ctx.parent:
        prepare_params(ctx.parent, params)

    params.update(ctx.params)

    return params


def run_command(ctx, clazz):
    params = prepare_params(ctx)
    Cekit(params).run(clazz)


def run_test(ctx, tester):
    if tester == 'behave':
        from cekit.test.behave_tester import BehaveTester as tester_impl
        LOGGER.info("Using Behave tester to test the image")
    else:
        raise CekitError("Tester engine {} is not supported".format(tester))

    run_command(ctx, tester_impl)


def run_build(ctx, builder):
    if builder == 'docker':
        # import is delayed until here to prevent circular import error
        from cekit.builders.docker_builder import DockerBuilder as builder_impl
        LOGGER.info("Using Docker builder to build the image")
    elif builder == 'osbs':
        # import is delayed until here to prevent circular import error
        from cekit.builders.osbs import OSBSBuilder as builder_impl
        LOGGER.info("Using OSBS builder to build the image")
    elif builder == 'podman':
        from cekit.builders.podman import PodmanBuilder as builder_impl
        LOGGER.info("Using Podman builder to build the image")
    elif builder == 'buildah':
        from cekit.builders.buildah import BuildahBuilder as builder_impl
        LOGGER.info("Using Buildah builder to build the image")
    else:
        raise CekitError("Builder engine {} is not supported".format(builder))

    run_command(ctx, builder_impl)


class Cekit(object):
    """ Main application """

    def __init__(self, params):
        self.params = params

    def init(self):
        """ Initialize logging """
        if self.params.nocolor:
            setup_logging(False)
        else:
            setup_logging()
        if self.params.verbose:
            LOGGER.setLevel(logging.DEBUG)
        else:
            LOGGER.setLevel(logging.INFO)

        LOGGER.debug("Running version {}".format(__version__))

        if 'dev' in __version__ or 'rc' in __version__:
            LOGGER.warning("You are running unreleased development version of CEKit, "
                           "use it only at your own risk!")

    def configure(self):
        """
        Prepare CEKit configuration based on config file
        and provided common parameters via CLI
        """
        LOGGER.debug("Configuring CEKit...")

        CONFIG.configure(self.params.config,
                         {
                             'redhat': self.params.redhat,
                             'work_dir': self.params.work_dir
                         })

    def cleanup(self):
        """ Prepares target/image directory to be regenerated."""
        directories_to_clean = [os.path.join(self.params.target, 'image', 'modules'),
                                os.path.join(self.params.target, 'image', 'repos'),
                                os.path.join(self.params.target, 'repo')]

        for directory in directories_to_clean:
            if os.path.exists(directory):
                LOGGER.debug("Removing dirty directory: '{}'".format(directory))
                try:
                    shutil.rmtree(directory)
                except:
                    raise CekitError("Unable to clean directory '{}'".format(directory))

    def run(self, clazz):
        """ Main application entry """

        self.init()
        self.configure()
        self.cleanup()

        command = clazz(self.params)

        try:
            command.execute()
            LOGGER.info("Finished!")
            sys.exit(0)
        except KeyboardInterrupt:
            pass
        except CekitError as ex:
            if self.params.verbose:
                LOGGER.exception(ex)
            else:
                LOGGER.error(ex.message)
            sys.exit(1)


if __name__ == '__main__':
    cli()  # pylint: disable=no-value-for-parameter
