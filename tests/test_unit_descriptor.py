import yaml

from concreate.descriptor import Label, Port, Env, Volume, Packages, Image, Osbs


def test_label():
    label = Label(yaml.safe_load("""
      name: "io.k8s.display-name"
      value: "JBoss A-MQ 6.2"
"""))
    assert label['name'] == "io.k8s.display-name"
    assert label['value'] == "JBoss A-MQ 6.2"


def test_env():
    env = Env(yaml.safe_load("""
      name: "io.k8s.display-name"
      value: "JBoss A-MQ 6.2"
"""))
    assert env['name'] == "io.k8s.display-name"
    assert env['value'] == "JBoss A-MQ 6.2"


def test_port():
    env = Port(yaml.safe_load("""
      value: 8788
      expose: False
"""))
    assert env['value'] == 8788
    assert env['name'] == 8788
    assert not env['expose']


def test_volume():
    volume = Volume(yaml.safe_load("""
    name: vol1
    path: /tmp/a
"""))
    assert volume['name'] == 'vol1'
    assert volume['path'] == '/tmp/a'


def test_volume_name():
    volume = Volume(yaml.safe_load("""
    path: /tmp/a
"""))
    assert volume['name'] == 'a'
    assert volume['path'] == '/tmp/a'


def test_osbs():
    osbs = Osbs(yaml.safe_load("""
    repository:
      name: foo
      branch: bar
"""))

    assert osbs['repository']['name'] == 'foo'
    assert osbs['repository']['branch'] == 'bar'


def test_packages():
    pkg = Packages(yaml.safe_load("""
      repositories:
          - repo-foo
          - repo-bar
      install:
          - pkg-foo"""))

    assert 'repo-foo' in pkg['repositories']
    assert 'repo-bar' in pkg['repositories']
    assert 'pkg-foo' in pkg['install']


def test_image():
    image = Image(yaml.safe_load("""
    from: foo
    name: test/foo
    version: 1.9
    labels:
      - name: test
        value: val1
      - name: label2
        value: val2
    envs:
      - name: env1
        value: env1val
    """), 'foo')

    assert image['name'] == 'test/foo'
    assert type(image['labels'][0]) == Label
    assert image['labels'][0]['name'] == 'test'
