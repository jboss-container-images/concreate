import logging
import os
import sys
import subprocess
import yaml

from cekit.errors import CekitError

try:
    basestring
except NameError:
    basestring = str

logger = logging.getLogger('cekit')


class Map(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


def load_descriptor(descriptor):
    """ parses descriptor and validate it against requested schema type

    Args:
      descriptor - yaml descriptor or path to a descriptor to be loaded.
      If a path is provided it must be an absolute path. In other case it's
      assumed that it is a yaml descriptor.

    Returns descriptor as a dictionary
    """

    try:
        data = yaml.safe_load(descriptor)
    except Exception as ex:
        raise CekitError('Cannot load descriptor', ex)

    if isinstance(data, basestring):
        logger.debug("Reading descriptor from '{}' file...".format(descriptor))

        if os.path.exists(descriptor):
            with open(descriptor, 'r') as fh:
                return yaml.safe_load(fh)

        raise CekitError(
            "Descriptor could not be found on the '{}' path, please check your arguments!".format(descriptor))

    logger.debug("Reading descriptor directly...")

    return data


def decision(question):
    """Asks user for a question returning True/False answed"""
    if sys.version_info[0] < 3:
        if raw_input("\n%s [Y/n] " % question) in ["", "y", "Y"]:
            return True
    else:
        if input("\n%s [Y/n] " % question) in ["", "y", "Y"]:
            return True

    return False


def get_brew_url(md5):
    try:
        logger.debug("Getting brew details for an artifact with '%s' md5 sum" % md5)
        list_archives_cmd = ['brew', 'call', '--json-output', 'listArchives',
                             'checksum=%s' % md5, 'type=maven']
        logger.debug("Executing '%s'." % " ".join(list_archives_cmd))
        archive_yaml = yaml.safe_load(subprocess.check_output(list_archives_cmd))

        if not archive_yaml:
            raise CekitError("Artifact with md5 checksum %s could not be found in Brew" % md5)

        archive = archive_yaml[0]
        build_id = archive['build_id']
        filename = archive['filename']
        group_id = archive['group_id']
        artifact_id = archive['artifact_id']
        version = archive['version']

        get_build_cmd = ['brew', 'call', '--json-output', 'getBuild', 'buildInfo=%s' % build_id]
        logger.debug("Executing '%s'" % " ".join(get_build_cmd))
        build = yaml.safe_load(subprocess.check_output(get_build_cmd))

        build_states = ['BUILDING', 'COMPLETE', 'DELETED', 'FAILED', 'CANCELED']

        # State 1 means: COMPLETE which is the only success state. Other states are:
        #
        # 'BUILDING': 0
        # 'COMPLETE': 1
        # 'DELETED': 2
        # 'FAILED': 3
        # 'CANCELED': 4
        if build['state'] != 1:
            raise CekitError(
                "Artifact with checksum {} was found in Koji metadata but the build is in incorrect state ({}) making the artifact not available for downloading anymore".format(md5, build_states[build['state']]))

        package = build['package_name']
        release = build['release']

        url = 'http://download.devel.redhat.com/brewroot/packages/' + package + '/' + \
            version.replace('-', '_') + '/' + release + '/maven/' + \
            group_id.replace('.', '/') + '/' + \
            artifact_id.replace('.', '/') + '/' + version + '/' + filename
    except subprocess.CalledProcessError as ex:
        logger.error("Can't fetch artifacts details from brew: '%s'." %
                     ex.output)
        raise ex
    return url


class Chdir(object):
    """ Context manager for changing the current working directory """

    def __init__(self, newPath):
        self.newPath = os.path.expanduser(newPath)

    def __enter__(self):
        self.savedPath = os.getcwd()
        os.chdir(self.newPath)

    def __exit__(self, etype, value, traceback):
        os.chdir(self.savedPath)


class DependencyHandler(object):
    """
    External dependency manager. Understands on what platform are we currently
    running and what dependencies are required to be installed to satisfy the
    requirements.
    """

    # List of operating system families on which Cekit is known to work.
    # It may work on other operating systems too, but it was not tested.
    KNOWN_OPERATING_SYSTEMS = ['fedora', 'centos', 'rhel']

    # Set of core Cekit external dependencies.
    # Format is defined below, in the handle_dependencies() method
    EXTERNAL_CORE_DEPENDENCIES = {
        'git': {
            'package': 'git',
            'executable': 'git'
        }
    }

    def __init__(self):
        self.os_release = {}
        self.platform = None

        os_release_path = "/etc/os-release"

        if os.path.exists(os_release_path):
            # Read the file containing operating system information
            with open(os_release_path, 'r') as f:
                content = f.readlines()

            self.os_release = dict(l.strip().split('=') for l in content)

            # Remove the quote character, if it's there
            for key in self.os_release.keys():
                self.os_release[key] = self.os_release[key].strip('"')

        if not self.os_release or 'ID' not in self.os_release or 'NAME' not in self.os_release or 'VERSION' not in self.os_release:
            logger.warning(
                "You are running Cekit on an unknown platform. External dependencies suggestions may not work!")
            return

        self.platform = self.os_release['ID']

        if self.os_release['ID'] not in DependencyHandler.KNOWN_OPERATING_SYSTEMS:
            logger.warning(
                "You are running Cekit on an untested platform: {} {}. External dependencies suggestions will not work!".format(self.os_release['NAME'], self.os_release['VERSION']))
            return

        logger.info("You are running on known platform: {} {}".format(
            self.os_release['NAME'], self.os_release['VERSION']))

    def _handle_dependencies(self, dependencies):
        """
        The dependencies provided is expected to be a dict in following format:

        {
            PACKAGE_ID: { 'package': PACKAGE_NAME, 'command': COMMAND_TO_TEST_FOR_PACKACGE_EXISTENCE },
        }

        Additionally every package can contain platform specific information, for example:

        {
            'git': {
                'package': 'git',
                'executable': 'git',
                'fedora': {
                    'package': 'git-latest'
                }
            }
        }

        If the platform on which Cekit is currently running is available, it takes precedence before
        defaults.
        """

        if not dependencies:
            logger.debug("No dependencies found, skipping...")
            return

        for dependency in dependencies.keys():
            current_dependency = dependencies[dependency]

            package = current_dependency.get('package')
            library = current_dependency.get('library')
            executable = current_dependency.get('executable')

            if self.platform in current_dependency:
                package = current_dependency[self.platform].get('package', package)
                library = current_dependency[self.platform].get('library', library)
                executable = current_dependency[self.platform].get('executable', executable)

            logger.debug("Checking if '{}' dependency is provided...".format(dependency))

            if library:
                if self._check_for_library(dependency, library):
                    logger.debug("Required Cekit library '{}' was found as a '{}' module!".format(
                        dependency, library))
                    continue
                else:
                    msg = "Required Cekit library '{}' was not found; required module '{}' could not be found.".format(
                        dependency, library)

                    # Library was not found, check if we have a hint
                    if package and self.platform in DependencyHandler.KNOWN_OPERATING_SYSTEMS:
                        msg += " Try to install the '{}' package.".format(package)

                    raise CekitError(msg)

            if executable:
                if package and self.platform in DependencyHandler.KNOWN_OPERATING_SYSTEMS:
                    self._check_for_executable(dependency, executable, package)
                else:
                    self._check_for_executable(dependency, executable)

        logger.debug("All dependencies provided!")

    # pylint: disable=R0201
    def _check_for_library(self, dependency, library):
        library_found = False

        if sys.version_info[0] < 3:
            import imp
            try:
                imp.find_module(library)
                library_found = True
            except ImportError:
                pass
        else:
            import importlib
            if importlib.util.find_spec(library):
                library_found = True

        return library_found

    # pylint: disable=R0201
    def _check_for_executable(self, dependency, executable, package=None):
        path = os.environ.get("PATH", os.defpath)
        path = path.split(os.pathsep)

        for directory in path:
            file_path = os.path.join(os.path.normcase(directory), executable)

            if os.path.exists(file_path) and os.access(file_path, os.F_OK | os.X_OK) and not os.path.isdir(file_path):
                logger.debug("Cekit dependency '{}' provided via the '{}' executable.".format(
                    dependency, file_path))
                return

        msg = "Cekit dependency: '{}' was not found, please provide the '{}' executable.".format(
            dependency, executable)

        if package:
            msg += " To satisfy this requrement you can install the '{}' package.".format(package)

        raise CekitError(msg)

    def handle_core_dependencies(self):
        self._handle_dependencies(
            DependencyHandler.EXTERNAL_CORE_DEPENDENCIES)

    def handle(self, o):
        """
        Handles dependencies from selected object. If the object has 'dependencies' method,
        it will be called to retrieve a set of dependencies to check for.
        """

        if not o:
            return

        # Get the class of the object
        clazz = type(o)

        for var in [clazz, o]:
            # Check if a static method or variable 'dependencies' exists
            dependencies = getattr(var, "dependencies", None)

            if not dependencies:
                continue

            # Check if we have a method
            if callable(dependencies):
                # Execute that method to get list of dependecies and try to handle them
                self._handle_dependencies(o.dependencies())
                return
