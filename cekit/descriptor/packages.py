import logging
import os

import yaml

from cekit.config import Config
from cekit.descriptor import Descriptor
from cekit.descriptor.resource import create_resource
from cekit.errors import CekitError

logger = logging.getLogger('cekit')
config = Config()

packages_schema = yaml.safe_load("""
map:
  content_sets: {type: any}
  content_sets_file: {type: str}
  repositories:
    seq:
      - {type: any}
  install:
    seq:
      - {type: any}
  manager: {type: str, enum: ['yum', 'dnf', 'microdnf', 'apk', 'apt-get']}
  manager_flags: {type: str}""")


repository_schema = yaml.safe_load("""
map:
  name: {type: str, required: True}
  id: {type: str}
  present: {type: bool}
  url:
    map:
      repository: {type: str}
      gpg: {type: str}
  rpm: {type: str}
  description: {type: str}
  odcs:
    map:
     pulp: {type: str}
  filename: {type: str}
  """)


class Packages(Descriptor):
    """
    Object representing packages

    Args:
      descriptor - yaml containing Packages section
    """

    def __init__(self, descriptor, descriptor_path):
        self.schema = packages_schema
        self.descriptor_path = descriptor_path
        super(Packages, self).__init__(descriptor)

        # If 'content_sets' and 'content_sets_file' are defined at the same time
        if set(['content_sets', 'content_sets_file']).issubset(set(descriptor.keys())):
            raise CekitError(
                "You cannot specify 'content_sets' and 'content_sets_file' together in the packages section!")

        # If the 'content_sets_file' key is set and is not None we need to read the specified
        # file and make it available in the 'content_sets' key. The 'content_sets_file' key is removed
        # afterwards.
        if descriptor.get('content_sets_file', None):
            content_sets_file = os.path.join(self.descriptor_path, descriptor['content_sets_file'])

            if not os.path.exists(content_sets_file):
                raise CekitError("'%s' file not found!" % content_sets_file)

            with open(content_sets_file, 'r') as file_:
                descriptor['content_sets'] = yaml.safe_load(file_)
            del descriptor['content_sets_file']

        self._prepare()

    def _prepare(self):
        package_manager = self._descriptor.get('manager')
        repositories = self._descriptor.get('repositories', [])

        if repositories and package_manager and package_manager not in ['yum', 'dnf', 'microdnf']:
            logger.warning(
                "Package manager {} does not support defining repositories, skipping all repositories".format(package_manager))
            self._descriptor['repositories'] = []
        else:
            self._descriptor['repositories'] = [Repository(x)
                                                for x in repositories]

        self._descriptor['install'] = self._descriptor.get('install', [])

    @property
    def manager(self):
        return self.get('manager')

    @property
    def manager_flags(self):
        return self.get('manager_flags')

    @property
    def repositories(self):
        return self.get('repositories')

    @property
    def install(self):
        return self.get('install')

    @property
    def content_sets(self):
        return self.get('content_sets')

    @content_sets.setter
    def content_sets(self, value):
        self._descriptor['content_sets'] = value
        self._descriptor.pop('content_sets_file', None)

    @property
    def content_sets_file(self):
        return self.get('content_sets_file')

    @content_sets_file.setter
    def content_sets_file(self, value):
        self._descriptor['content_sets_file'] = value
        self._descriptor.pop('content_sets', None)


class Repository(Descriptor):
    """Object representing package repository

    Args:
      descriptor - repository name as referenced in cekit config file
    """

    def __init__(self, descriptor):
        self.schema = repository_schema
        super(Repository, self).__init__(descriptor)

        if not (('url' in descriptor) ^
                ('odcs' in descriptor) ^
                ('id' in descriptor) ^
                ('rpm' in descriptor)):
            raise CekitError("Repository '%s' is invalid, you can use only one of "
                             "['id', 'odcs', 'rpm', 'url']"
                             % descriptor['name'])

        if 'filename' not in descriptor:
            descriptor['filename'] = '%s.repo' % descriptor['name'].replace(' ', '_')

        if 'url' not in descriptor:
            descriptor['url'] = {}

        # we don't want to merge any of these
        self.skip_merging = ['rpm',
                             'id',
                             'url']

        if 'present' not in self._descriptor:
            self._descriptor['present'] = True

    def fetch(self, target_dir):
        if not self._descriptor['url']['repository']:
            raise CekitError("Repository not defined for '{}'.".format(self.name))
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        create_resource({'url': self._descriptor['url']['repository']}) \
            .copy(os.path.join(target_dir, self._descriptor['filename']))

    @property
    def name(self):
        return self.get('name')

    @name.setter
    def name(self, value):
        self._descriptor['name'] = value

    @property
    def description(self):
        return self.get('description')

    @description.setter
    def description(self, value):
        self._descriptor['description'] = value

    @property
    def present(self):
        return self.get('present', True)

    @present.setter
    def present(self, value):
        self._descriptor['present'] = value

    @property
    def id(self):
        return self.get('id')

    @id.setter
    def id(self, value):
        self._descriptor['id'] = value
        self._descriptor.pop('url', None)
        self._descriptor.pop('rpm', None)
        self._descriptor.pop('odcs', None)
        self._descriptor.pop('filename', None)

    @property
    def url(self):
        return self.get('url')

    @url.setter
    def url(self, value):
        self._descriptor['url'] = value
        self._descriptor.pop('id', None)
        self._descriptor.pop('rpm', None)
        self._descriptor.pop('odcs', None)
        self._descriptor.pop('filename', None)

    @property
    def rpm(self):
        return self.get('rpm')

    @rpm.setter
    def rpm(self, value):
        self._descriptor['rpm'] = value
        self._descriptor.pop('id', None)
        self._descriptor.pop('url', None)
        self._descriptor.pop('odcs', None)
        self._descriptor.pop('filename', None)

    @property
    def odcs(self):
        return self.get('odcs')

    @odcs.setter
    def odcs(self, value):
        self._descriptor['odcs'] = value
        self._descriptor.pop('id', None)
        self._descriptor.pop('url', None)
        self._descriptor.pop('rpm', None)
        self._descriptor.pop('filename', None)

    @property
    def filename(self):
        return self.get('filename')

    @filename.setter
    def filename(self, value):
        self._descriptor['filename'] = value
        self._descriptor.pop('id', None)
        self._descriptor.pop('url', None)
        self._descriptor.pop('rpm', None)
        self._descriptor.pop('odcs', None)
