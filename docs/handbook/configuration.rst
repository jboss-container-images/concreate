Configuration file
=========================

CEKit can be configured using a configuration file. We use the
`ini file format <https://en.wikipedia.org/wiki/INI_file>`__.

CEKit will look for this file at the path ``~/.cekit/config``. Its location
can be changed via command line ``--config`` option.

Example
    Running CEKit with different config file:

    .. code-block:: bash

        $ cekit --config ~/alternative_path build

.. contents::
    :backlinks: none

Below you can find description of available sections together with options described in detail.

Common section
---------------

The ``[common]`` section contains settings used across CEKit.

Example
    .. code-block:: ini

        [common]
        work_dir = /tmp
        ssl_verify = False
        cache_url = http://cache.host.com/fetch?#algorithm#=#hash#
        redhat = True

Working directory
^^^^^^^^^^^^^^^^^^

Key
    ``work_dir``
Description
    Location of CEKit working directory, which is used to store some persistent data like
    dist-git repositories and artifact cache.
Default
    ``~/.cekit``
Example
    .. code-block:: ini

        [common]
        work_dir=/tmp


SSL verification
^^^^^^^^^^^^^^^^^

Key
    ``ssl_verify``
Description
    Controls verification of SSL certificates, for example when downloading artifacts.
Default
    ``True``
Example
    .. code-block:: ini

        [common]
        ssl_verify = False

Cache URL
^^^^^^^^^^^^^^^^^

Key
    ``cache_url``
Description
    Specifies a different location that could be used to fetch artifacts. Usually this is a URL to some cache service.

    You can use following substitutions:

    * ``#filename#`` -- the file name from the url of the artifact
    * ``#algorithm#`` -- has algorithm specified for the selected artifact
    * ``#hash#`` -- value of the digest.
Default
    Not set
Example
    Consider you have an image definition with artifacts section like this:

    .. code-block:: yaml

        artifacts:
            - url: "http://some.host.com/7.0.0/jboss-eap-7.0.0.zip"
              md5: cd02482daa0398bf5500e1628d28179a

    If we set the ``cache_url`` parameter in following way:

    .. code-block:: ini

        [common]
        cache_url = http://cache.host.com/fetch?#algorithm#=#hash#

    The JBoss EAP artifact will be fetched from: ``http://cache.host.com/fetch?md5=cd02482daa0398bf5500e1628d28179a``.

    And if we do it like this:

    .. code-block:: ini

        [common]
        cache_url = http://cache.host.com/cache/#filename#

    The JBoss EAP artifact will be fetched from: ``http://cache.host.com/cache/jboss-eap-7.0.0.zip``.

Red Hat environment
^^^^^^^^^^^^^^^^^^^^

Key
    ``redhat``
Description
    This option changes CEKit default options to comply with Red Hat internal infrastructure and policies.

    .. tip::
        Read more about :doc:`Red Hat environment </handbook/redhat>`.
Default
    ``False``
Example
    .. code-block:: ini

        [common]
        redhat = True


OSBS URL Restriction
^^^^^^^^^^^^^^^^^^^^

Key
    ``fetch_url_domains``
Description
    This option is used during OSBS processing to constrain the files added to ``fetch-artifacts-url``. It may be set to a comma separated list of URLs. If set, each potential URL based artifact to be added to ``fetch-artifacts-url`` must be within one of the URL domain/paths specified by this key. If not set then **all** URLs are added without restriction.

Default
    not set
Example
    .. code-block:: ini

        [common]
        fetch_url_domains = https://www.foo.bar/my-path,https://www.example.com

