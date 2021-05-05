import json
import logging
import os
import shutil
import ssl
import subprocess

try:
    from urllib.parse import urlparse
    from urllib.request import urlopen
except ImportError:
    from urlparse import urlparse
    from urllib2 import urlopen

from cekit.config import Config
from cekit.crypto import SUPPORTED_HASH_ALGORITHMS, check_sum
from cekit.descriptor import Descriptor
from cekit.errors import CekitError
from cekit.tools import get_brew_url, Map, Chdir

logger = logging.getLogger('cekit')
config = Config()

artifact_dest = '/tmp/artifacts/'


def create_resource(descriptor, **kwargs):
    """
    Module method responsible for instantiating proper resource object
    based on the provided descriptor.

    In most cases, only descriptor is required to create the object from descriptor.
    In case additional data is required, the kwargs 'dictionary' will be checked
    if the required key exists and will be used in the object constructor.
    """

    if 'image' in descriptor:
        return _ImageContentResource(descriptor)

    if 'path' in descriptor:
        directory = kwargs.pop('directory')

        if not directory:
            raise CekitError(("Internal error: cannot instantiate PathResource: {}, directory was not provided, " +
                              "please report it: https://github.com/cekit/cekit/issues").format(descriptor))

        return _PathResource(descriptor, directory)

    if 'url' in descriptor:
        return _UrlResource(descriptor)

    if 'git' in descriptor:
        return _GitResource(descriptor)

    if 'md5' in descriptor:
        return _PlainResource(descriptor)

    raise CekitError("Resource '{}' is not supported".format(descriptor))


class Resource(Descriptor):
    """
    Base class for handling resources.

    In most cases resources are synonym to artifacts.
    """

    CHECK_INTEGRITY = True

    def __init__(self, descriptor):
        # Schema must be provided by the implementing class
        if not self.schema:
            raise CekitError("Resource '{}' has no schema defined".format(type(self).__name__))

        # Includes validation
        super(Resource, self).__init__(descriptor)

        # Make sure the we have 'name' set
        self._ensure_name(descriptor)
        # Make sure the we have 'target' set
        self._ensure_target(descriptor)
        # Add a single slash at the end of the 'dest' value
        self._normalize_dest(descriptor)
        # Convert the dictionary into a Map object for easier access
        self._descriptor = self.__to_map(descriptor)

        self.skip_merging = ['md5', 'sha1', 'sha256', 'sha512']

        # forwarded import to prevent circular imports
        from cekit.cache.artifact import ArtifactCache
        self.cache = ArtifactCache()

    def __to_map(self, dictionary):
        """
        Convert provided dictionary, recursively, into a Map object.

        This will make it possible to access nested elements
        via properties:

                res.git.url

        instead of:

                res.git['url]
        """
        if not isinstance(dictionary, dict):
            return dictionary

        converted = Map()

        for key in dictionary:
            converted[key] = self.__to_map(dictionary[key])

        return converted

    def __eq__(self, other):
        # All subclasses of Resource are considered same object type
        if isinstance(other, Resource):
            return self['name'] == other['name']
        return NotImplemented

    def __ne__(self, other):
        # All subclasses of Resource are considered same object type
        if isinstance(other, Resource):
            return not self['name'] == other['name']
        return NotImplemented

    def _ensure_name(self, descriptor):
        """
        Makes sure the 'name' attribute exists.

        If it does not, a default value will be computed based on the implementation
        type of the resource class.
        """

        # If the 'name' key is present and there is a value, we have nothing to do
        if descriptor.get('name') is not None:
            return

        # Get the default value set for particular resource type
        default = self._get_default_name_value(descriptor)  # pylint: disable=assignment-from-none

        # If there is still no default, we need to fail, because 'name' is required.
        # If we ever get here, it is a bug and should be reported.
        if not default:
            raise CekitError(
                ("Internal error: no value found for 'name' in '{}' artifact; unable to generate default value, " +
                 "please report it: https://github.com/cekit/cekit/issues").format(descriptor))

        logger.warning("No value found for 'name' in '{}' artifact; using auto-generated value of '{}'".
                       format(json.dumps(descriptor, sort_keys=True), default))

        descriptor['name'] = default

    def _ensure_target(self, descriptor):
        if descriptor.get('target') is not None:
            return

        descriptor['target'] = self._get_default_target_value(descriptor)

    def _normalize_dest(self, descriptor):
        """
        Make sure that the 'dest' value, if provided, does end with a single slash.
        """

        if descriptor.get('dest') is not None:
            descriptor['dest'] = os.path.normpath(descriptor.get('dest')) + '/'

    def _get_default_name_value(self, descriptor):  # pylint: disable=unused-argument
        """
        Returns default identifier value for particular class.

        This method must be overridden in classes extending Resource.
        Returned should be a string that will be be a unique identifier
        of the resource across thw whole image.
        """
        return None

    def _get_default_target_value(self, descriptor):  # pylint: disable=unused-argument
        return os.path.basename(descriptor.get('name'))

    def _copy_impl(self, target):
        raise NotImplementedError("Implement _copy_impl() for Resource: " +
                                  self.__module__ + "." +
                                  type(self).__name__)

    def copy(self, target=os.getcwd()):

        if os.path.isdir(target):
            target = os.path.join(target, self.target)

        logger.info("Copying resource '{}'...".format(self.name))

        if os.path.exists(target) and self.__verify(target):
            logger.debug("Local resource '{}' exists and is valid".format(self.name))
            return target

        cached_resource = self.cache.cached(self)

        if cached_resource:
            shutil.copy(cached_resource['cached_path'],
                        target)
            logger.info("Using cached artifact '{}'.".format(self.name))

        else:
            try:
                self.cache.add(self)
                cached_resource = self.cache.get(self)
                shutil.copy(cached_resource['cached_path'],
                            target)
                logger.info("Using cached artifact '{}'.".format(self.name))
            except ValueError:
                return self.guarded_copy(target)

    def guarded_copy(self, target):
        try:
            self._copy_impl(target)
        except Exception as ex:
            logger.warning("Cekit is not able to fetch resource '{}' automatically. "
                           "Please use cekit-cache command to add this artifact manually.".format(self.name))

            if self.description:
                logger.info(self.description)

            # exception is fatal we be logged before Cekit dies
            raise CekitError("Error copying resource: '%s'. See logs for more info."
                             % self.name, ex)

        if set(SUPPORTED_HASH_ALGORITHMS).intersection(self) and \
                not self.__verify(target):
            raise CekitError('Artifact checksum verification failed!')

        return target

    def __verify(self, target):
        """ Checks all defined check_sums for an aritfact """
        if not set(SUPPORTED_HASH_ALGORITHMS).intersection(self):
            logger.debug("Artifact '{}' lacks any checksum definition.".format(self.name))
            return False
        if not Resource.CHECK_INTEGRITY:
            logger.info("Integrity checking disabled, skipping verification.")
            return True
        if os.path.isdir(target):
            logger.info("Target is directory, cannot verify checksum.")
            return True
        for algorithm in SUPPORTED_HASH_ALGORITHMS:
            if algorithm in self and self[algorithm]:
                if not check_sum(target, algorithm, self[algorithm], self['name']):
                    return False
        return True

    def __substitute_cache_url(self, url):
        cache = config.get('common', 'cache_url')

        if not cache:
            return url

        for algorithm in SUPPORTED_HASH_ALGORITHMS:
            if algorithm in self:
                logger.debug("Using {} checksum to fetch artifacts from cacher".format(algorithm))

                url = cache.replace('#filename#', self.name).replace(
                    '#algorithm#', algorithm).replace('#hash#', self[algorithm])

                logger.debug("Using cache url '{}'".format(url))

        return url

    def _download_file(self, url, destination, use_cache=True):
        """ Downloads a file from url and save it as destination """
        if use_cache:
            url = self.__substitute_cache_url(url)

        if not url:
            raise CekitError("Artifact %s cannot be downloaded, no URL provided" % self.name)

        logger.debug("Downloading from '{}' as {}".format(url, destination))

        parsed_url = urlparse(url)

        if parsed_url.scheme == 'file' or not parsed_url.scheme:
            if os.path.isdir(parsed_url.path):
                shutil.copytree(parsed_url.path, destination)
            else:
                shutil.copy(parsed_url.path, destination)
        elif parsed_url.scheme in ['http', 'https']:
            verify = config.get('common', 'ssl_verify')
            if str(verify).lower() == 'false':
                verify = False

            ctx = ssl.create_default_context()

            if not verify:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

            res = urlopen(url, context=ctx)

            if res.getcode() != 200:
                raise CekitError("Could not download file from %s" % url)

            try:
                with open(destination, 'wb') as f:
                    while True:
                        chunk = res.read(1048576)  # 1 MB
                        if not chunk:
                            break
                        f.write(chunk)
            except Exception:
                try:
                    logger.debug("Removing incompletely downloaded '{}' file".format(destination))
                    os.remove(destination)
                except OSError:
                    logger.warning("An error occurred while removing file '{}'".format(destination))

                raise
        else:
            raise CekitError("Unsupported URL scheme: {}".format(url))


class _PathResource(Resource):
    """
    Documentation: http://docs.cekit.io/en/latest/descriptor/image.html#path-artifacts
    """

    SCHEMA = {
        'map': {
            'name': {'type': 'str', 'desc': 'Key used to identify the resource'},
            'target': {'type': 'str', 'desc': 'Target file name for the resource'},
            'dest': {'type': 'str', 'desc': 'Destination directory inside of the container', 'default': artifact_dest},
            'description': {'type': 'str', 'desc': 'Description of the resource'},
            'path': {'type': 'str', 'required': True, 'desc': 'Relative (suggested) or absolute path to the resource'},
            'md5': {'type': 'str', 'desc': 'The md5 checksum of the resource'},
            'sha1': {'type': 'str', 'desc': 'The sha1 checksum of the resource'},
            'sha256': {'type': 'str', 'desc': 'The sha256 checksum of the resource'},
            'sha512': {'type': 'str', 'desc': 'The sha512 checksum of the resource'}
        }
    }

    def __init__(self, descriptor, directory):
        self.schema = _PathResource.SCHEMA

        super(_PathResource, self).__init__(descriptor)

        path = descriptor.get('path')

        # If the path is relative it's considered relative to the directory parameter
        if not os.path.isabs(path):
            self['path'] = os.path.join(directory, path)

    def _get_default_name_value(self, descriptor):
        """
        Default identifier is the last part (most probably file name) of the URL.
        """
        return os.path.basename(descriptor.get('path'))

    def _copy_impl(self, target):
        if not os.path.exists(self.path):
            cache = config.get('common', 'cache_url')

            # If cache_url is specified in Cekit configuration
            # file - try to fetch the 'path' artifact from cacher
            # even if it was not defined as 'url'.
            if cache:
                try:
                    self._download_file(self.path, target)
                    return target
                except Exception as ex:
                    logger.exception(ex)
                    raise CekitError("Could not download resource '%s' from cache" % self.name)
            else:
                raise CekitError("Could not copy resource '%s', "
                                 "source path does not exist. "
                                 "Make sure you provided correct path" % self.name)

        logger.debug("Copying repository from '{}' to '{}'.".format(self.path, target))
        if os.path.isdir(self.path):
            shutil.copytree(self.path, target)
        else:
            shutil.copy2(self.path, target)
        return target


class _UrlResource(Resource):
    """
    Documentation: http://docs.cekit.io/en/latest/descriptor/image.html#url-artifacts
    """

    SCHEMA = {
        'map': {
            'name': {'type': 'str', 'desc': 'Key used to identify the resource'},
            'target': {'type': 'str', 'desc': 'Target file name for the resource'},
            'dest': {'type': 'str', 'desc': 'Destination directory inside of the container', 'default': artifact_dest},
            'description': {'type': 'str', 'desc': 'Description of the resource'},
            'url': {'type': 'str', 'required': True, 'desc': 'URL where the resource can be found'},
            'md5': {'type': 'str', 'desc': 'The md5 checksum of the resource'},
            'sha1': {'type': 'str', 'desc': 'The sha1 checksum of the resource'},
            'sha256': {'type': 'str', 'desc': 'The sha256 checksum of the resource'},
            'sha512': {'type': 'str', 'desc': 'The sha512 checksum of the resource'}
        }
    }

    def __init__(self, descriptor):
        self.schema = _UrlResource.SCHEMA

        super(_UrlResource, self).__init__(descriptor)

        # Normalize the URL
        self['url'] = descriptor.get('url').strip()

    # Avoid protected access warning
    def download_file(self, url, destination):
        return self._download_file(url, destination, False)

    def _get_default_name_value(self, descriptor):
        """
        Default identifier is the last part (most probably file name) of the URL.
        """
        return os.path.basename(descriptor.get('url'))

    def _copy_impl(self, target):
        try:
            self._download_file(self.url, target)
        except:
            logger.debug("Cannot hit artifact: '{}' via cache, trying directly.".format(self.name))
            self._download_file(self.url, target, use_cache=False)
        return target


class _GitResource(Resource):

    SCHEMA = {
        'map': {
            'name': {'type': 'str', 'desc': 'Key used to identify the resource'},
            'target': {'type': 'str', 'desc': 'Target file name for the resource'},
            'description': {'type': 'str', 'desc': 'Description of the resource'},
            'git': {
                'required': True,
                'map': {
                    'url': {'type': 'str', 'required': True, 'desc': 'URL of the repository'},
                    'ref': {'type': 'str', 'required': True, 'desc': 'Reference to check out; could be branch, tag, etc'},
                }
            }
        }
    }

    def __init__(self, descriptor):
        self.schema = _GitResource.SCHEMA

        super(_GitResource, self).__init__(descriptor)

    def _get_default_name_value(self, descriptor):
        return os.path.basename(descriptor.get('git', {}).get('url')).split(".", 1)[0]

    def _copy_impl(self, target):
        cmd = ['git', 'clone', self.git.url, target]
        logger.debug("Cloning Git repository: '{}'".format(' '.join(cmd)))
        subprocess.check_output(cmd, stderr=subprocess.STDOUT)

        with Chdir(target):
            cmd = ['git', 'checkout', self.git.ref]
            logger.debug("Checking out '{}' ref: '{}'".format(self.git.ref, ' '.join(cmd)))
            subprocess.check_output(cmd, stderr=subprocess.STDOUT)

        return target


class _PlainResource(Resource):
    """
    Documentation: http://docs.cekit.io/en/latest/descriptor/image.html#plain-artifacts
    """

    SCHEMA = {
        'map': {
            'name': {'type': 'str', 'required': True, 'desc': 'Key used to identify the resource'},
            'target': {'type': 'str', 'desc': 'Target file name for the resource'},
            'dest': {'type': 'str', 'desc': 'Destination directory inside of the container', 'default': artifact_dest},
            'description': {'type': 'str', 'desc': 'Description of the resource'},
            'md5': {'type': 'str', 'required': True, 'desc': 'The md5 checksum of the resource'},
            'sha1': {'type': 'str', 'desc': 'The sha1 checksum of the resource'},
            'sha256': {'type': 'str', 'desc': 'The sha256 checksum of the resource'},
            'sha512': {'type': 'str', 'desc': 'The sha512 checksum of the resource'}
        }
    }

    def __init__(self, descriptor):
        self.schema = _PlainResource.SCHEMA

        super(_PlainResource, self).__init__(descriptor)

    def _copy_impl(self, target):
        # First of all try to download the file using cacher if specified
        if config.get('common', 'cache_url'):
            try:
                self._download_file(None, target)
                return target
            except Exception as e:
                logger.debug(str(e))
                logger.warning("Could not download '{}' artifact using cacher".format(self.name))

        # Next option is to download it from Brew directly but only if the md5 checkum
        # is provided and we are running with the --redhat switch
        if self.md5 and config.get('common', 'redhat'):
            logger.debug("Trying to download artifact '{}' from Brew directly".format(self.name))

            try:
                # Generate the URL
                url = get_brew_url(self.md5)
                # Use the URL to download the file
                self._download_file(url, target, use_cache=False)
                return target
            except Exception as e:
                logger.debug(str(e))
                logger.warning("Could not download artifact '{}' from Brew".format(self.name))

        raise CekitError("Artifact {} could not be found".format(self.name))


class _ImageContentResource(Resource):
    """
    Class to cover artifacts that should be fetched from images.

    Main purpose of this type of resources are artifacts built as
    part of multi-stage builds. Other use case is where the artifact
    should be fetched from an already built image.

    Such a resource is represented in Dockerfile as:

        COPY --from=[IMAGE] [PATH] /tmp/artifacts/[NAME]

    Due to the nature of such resources, we're not able to validate
    checksums of such resources.
    """

    SCHEMA = {
        'map': {
            'name': {'type': 'str', 'desc': 'Key used to identify the resource'},
            'target': {'type': 'str', 'desc': 'Target file name for the resource'},
            'dest': {'type': 'str', 'desc': 'Destination directory inside of the container', 'default': '/tmp/artifacts/'},
            'description': {'type': 'str', 'desc': 'Description of the resource'},
            'image': {'type': 'str', 'required': True, 'desc': 'Name of the image which holds the resource'},
            'path': {'type': 'str', 'required': True, 'desc': 'Path in the image under which the resource can be found'}
        }
    }

    def __init__(self, descriptor):
        self.schema = _ImageContentResource.SCHEMA

        super(_ImageContentResource, self).__init__(descriptor)

    def _get_default_name_value(self, descriptor):
        """
        Default identifier is the file name of the resource inside of the image.
        """
        return os.path.basename(descriptor.get('path'))

    def _copy_impl(self, target):
        """
        For stage artifacts, there is nothing to copy, because the artifact is located
        in an image that should be built in earlier stage of the image build process.
        """
        return target
