import fileinput
import logging
import os
import sys
import tempfile

import yaml

from cekit import crypto
from cekit.config import Config
from cekit.descriptor.resource import _PlainResource, _UrlResource
from cekit.generator.base import Generator
from cekit.tools import get_brew_url, copy_recursively

logger = logging.getLogger('cekit')
config = Config()


class OSBSGenerator(Generator):
    def __init__(self, descriptor_path, target, overrides):
        self._wipe = True
        super(OSBSGenerator, self).__init__(descriptor_path, target, overrides)

    def init(self):
        super(OSBSGenerator, self).init()

        self._prepare_container_yaml()

    def generate(self, builder):
        # If extra directory exists (by default named 'osbs_extra') next to
        # the image descriptor, copy it contents to the target directory.
        #
        # https://github.com/cekit/cekit/issues/394
        copy_recursively(
            os.path.join(os.path.dirname(self._descriptor_path), self.image.osbs.extra_dir),
            os.path.join(self.target, os.path.join('image', self.image.osbs.extra_dir))
        )
        super(OSBSGenerator, self).generate(builder)

    def _prepare_content_sets(self, content_sets):
        content_sets_f = os.path.join(self.target, 'image', 'content_sets.yml')

        if not os.path.exists(os.path.dirname(content_sets_f)):
            os.makedirs(os.path.dirname(content_sets_f))

        with open(content_sets_f, 'w') as _file:
            yaml.safe_dump(content_sets, _file, default_flow_style=False)

    def _prepare_container_yaml(self):
        container_f = os.path.join(self.target, 'image', 'container.yaml')
        container = self.image.get('osbs', {}).get('configuration', {}).get('container')

        if not container:
            # No container definition in current image; check if one in multi-stage.
            for i in self.builder_images:
                container = i.get('osbs', {}).get('configuration', {}).get('container', {})
                if container:
                    break
        if not container:
            return

        if not os.path.exists(os.path.dirname(container_f)):
            os.makedirs(os.path.dirname(container_f))

        with open(container_f, 'w') as _file:
            yaml.safe_dump(container, _file, default_flow_style=False)

    def _prepare_repository_rpm(self, repo):
        # no special handling is needed here, everything is in template
        pass

    def prepare_artifacts(self):
        """Goes through artifacts section of image descriptor
        and fetches all of them
        """

        logger.info("Handling artifacts for OSBS...")
        target_dir = os.path.join(self.target, 'image')
        fetch_artifacts_url = []
        url_description = {}

        for image in self.images:
            for artifact in image.all_artifacts:
                logger.info("Preparing artifact '{}' (of type {})".format(artifact['name'], type(artifact)))

                if isinstance(artifact, _UrlResource):
                    intersected_hash = [x for x in crypto.SUPPORTED_HASH_ALGORITHMS if x in artifact]
                    logger.debug("Found checksum markers of {}".format(intersected_hash))
                    if not intersected_hash:
                        logger.warning("No md5 supplied for {}, calculating from the remote artifact".format(artifact['url']))
                        intersected_hash = ["md5"]
                        tmpfile = tempfile.NamedTemporaryFile()
                        try:
                            artifact.download_file(artifact['url'], tmpfile.name)
                            artifact["md5"] = crypto.get_sum(tmpfile.name, "md5")
                        finally:
                            tmpfile.close()

                    fetch_artifacts_url.append({'url': artifact['url'],
                                                'target': os.path.join(artifact['target'])})
                    for c in intersected_hash:
                        fetch_artifacts_url[len(fetch_artifacts_url) - 1].update({c: artifact[c]})
                    if 'description' in artifact:
                        url_description[artifact['url']] = artifact['description']
                    logger.debug(
                        "Artifact '{}' (as URL) added to fetch-artifacts-url.yaml with contents {}".format(
                            artifact['target'], fetch_artifacts_url[len(fetch_artifacts_url) - 1]))
                    # OSBS by default downloads all artifacts to artifacts/<target_path>
                    artifact['target'] = os.path.join('artifacts', artifact['target'])
                elif isinstance(artifact, _PlainResource) and config.get('common', 'redhat'):
                    try:
                        fetch_artifacts_url.append({'md5': artifact['md5'],
                                                    'url': get_brew_url(artifact['md5']),
                                                    'target': os.path.join(artifact['target'])})
                        logger.debug(
                            "Artifact '{}' (as plain) added to fetch-artifacts-url.yaml".format(artifact['target']))
                        # OSBS by default downloads all artifacts to artifacts/<target_path>
                        artifact['target'] = os.path.join('artifacts', artifact['target'])
                    except:
                        logger.warning("Plain artifact {} could not be found in Brew, trying to handle it using lookaside cache".
                                       format(artifact['name']))
                        artifact.copy(target_dir)
                        # TODO: This is ugly, rewrite this!
                        artifact['lookaside'] = True

                else:
                    logger.debug("Copying artifact {} to {}".format(artifact, target_dir))
                    artifact.copy(target_dir)

        fetch_artifacts_file = os.path.join(self.target, 'image', 'fetch-artifacts-url.yaml')

        if fetch_artifacts_url:
            with open(fetch_artifacts_file, 'w') as _file:
                yaml.safe_dump(fetch_artifacts_url, _file, default_flow_style=False)
            if config.get('common', 'redhat'):
                for key, value in url_description.items():
                    logger.debug("Processing to add build references for {} -> {}".format(key, value))
                    for line in fileinput.input(fetch_artifacts_file, inplace=1):
                        line = line.replace(key, key + ' # ' + value)
                        sys.stdout.write(line)
        logger.debug("Artifacts handled")
