# Assayist

A system for discovering and tracing the composition of shipped products.

## Development

To setup a development environment:
* Create and activate a [Python virtual environment](https://docs.python.org/3/library/venv.html)
    (Python 3.6 or later is required):
  ```bash
  $ python3 -m venv --system-site-packages venv
  ```
* Start an instance of a [Neo4j](https://neo4j.com/docs/operations-manual/current/installation/docker/)
    database:
  ```bash
  $ sudo docker run --publish=7474:7474 --publish=7687:7687 neo4j:3.3
  ```
* Install the API and its dependencies with:
  ```bash
  $ python setup.py develop
  ```

## Run the Unit Tests

Since the unit tests require a running Neo4j instance, the tests are run in Docker containers using
Docker Compose. The commands required to run the unit tests are abstracted in
`scripts/run-tests.sh`. This script will create the Docker image required to run the tests based
on `docker/Dockerfile-tests`, create a container with Neo4j, create another container to run
the tests based on the built Docker image, run the tests, and then delete the two created
containers.

To install Docker and Docker Compose on Fedora, run:

```bash
$ sudo dnf install docker docker-compose
```

To start Docker, run:

```bash
$ sudo systemctl start docker
```

To run the tests, run:

```bash
$ sudo scripts/run-tests.sh
```

To run just a single test, you can run:

```bash
$ sudo scripts/run-tests.sh pytest3 -vvv tests/test_file::test_name
```

## Code Styling

The codebase conforms to the style enforced by `flake8` with the following exceptions:
* The maximum line length allowed is 100 characters instead of 80 characters

In addition to `flake8`, docstrings are also enforced by the plugin `flake8-docstrings` with
the following exemptions:
* D100: Missing docstring in public module
* D104: Missing docstring in public package

The format of the docstrings should be in the Sphynx style such as:

```
Get a resource from Neo4j.

:param str resource: a resource name that maps to a neomodel class
:param str uid: the value of the UniqueIdProperty to query with
:return: a Flask JSON response
:rtype: flask.Response
:raises NotFound: if the item is not found
:raises ValidationError: if an invalid resource was requested
```

## Running the Processor

Using a container is the preferred method for running the Assayist processor. There is a
[Dockerfile](docker/Dockerfile) included in this repository, and it accepts two arguments. The
first argument is `rcm_tools_repo_file`, which should be a link to a DNF repo file that includes
the required builds not available (e.g. `brewkoji`) in the official Fedora repos. The second
argument is `ca_file`, which should be a link to the internal CA that Assayist must trust for the
processors to run successfully.

To build the container image, run the following in your cloned repository:
```bash
$ sudo docker build \
    --build-arg rcm_tools_repo_file=https://domain.local/path/to/repo.repo \
    --build-arg ca_file=https://domain.local/path/to/ca.crt \
    -f docker/Dockerfile .
```
