# SPDX-License-Identifier: GPL-3.0+

import collections

import neomodel

from assayist.common.models.content import Build
from assayist.client.error import NotFound, InvalidInput


def set_connection(neo4j_url):
    """
    Set the Neo4j connection string.

    :param str neo4j_url: the Neo4j connection string to configure neomodel with
    """
    neomodel.db.set_connection(neo4j_url)


def get_container_content_sources(build_id):
    """
    Get the sources used by the content in the container image.

    :param int build_id: the Koji build's ID
    :return: a list of source URLs
    :rtype: list
    """
    build = Build.nodes.get_or_none(id_=str(build_id))
    if not build:
        raise NotFound('The requested build does not exist in the database')

    # Bypass neomodel and use cypher directly for better performance
    internal_query = """
        MATCH (:Build {{id: '{0}'}})-[:PRODUCED]->(:Artifact)-[:EMBEDS]-(:Artifact)
            <-[:PRODUCED]-(:Build)-[:BUILT_FROM]->(internal:SourceLocation)
        OPTIONAL MATCH (internal)-[:UPSTREAM]->(upstream:SourceLocation)
        RETURN internal.url, upstream.url;
    """.format(build_id)
    results, _ = neomodel.db.cypher_query(internal_query)
    internal_urls = []
    upstream_urls = []
    for result in results:
        internal_urls.append(result[0])
        upstream_urls.append(result[1])
    return {
        'internal_urls': internal_urls,
        'upstream_urls': upstream_urls
    }


def get_current_and_previous_versions(name, type_, version):
    """
    Find the current and previous source locations.

    :param str name: the canonical name of the component
    :param str type_: the canonical type of the component
    :param str version: the canonical version of the source location
    :return: a dictionary of all the previous source locations and the current source location
    :rtype: dict
    """
    # TODO: Consider alternative names as well
    query = """
        MATCH (:Component {{canonical_name: '{name}', canonical_type: '{type}'}})
            <-[:SOURCE_FOR]-(:SourceLocation {{canonical_version: '{version}'}})
            -[:SUPERSEDES*0..]->(sl:SourceLocation)
        RETURN sl
    """.format(name=name, type=type_, version=version)
    results, _ = neomodel.db.cypher_query(query)
    rv = []
    for result in results:
        rv.append(dict(result[0]))
    return rv


def get_container_built_with_sources(source_locations):
    """
    Match container builds that used the input source locations to build the content in the image.

    :param list source_locations: a list of source location dictionaries to match against
    :return: a list of affected container build Koji IDs
    :rtype: list
    """
    if not source_locations or not isinstance(source_locations, collections.Iterable):
        raise InvalidInput('The input must be a list of source locations')

    query = """
        // First get all the input source locations
        MATCH (input_sl:SourceLocation) WHERE input_sl.url IN [{0}]
        // Then find all the source locations that are upstream or downstream of the input source
        // locations recursively. The resulting `sl` variable has all the input source locations
        // and all the upstream or downstream source locations of the input source locations.
        MATCH (input_sl)-[:UPSTREAM*0..]-(sl:SourceLocation)
        // Then find all the source locations that embed the source locations in `sl` recursively.
        // The resulting `sl` variable will have the contents of the `sl` variable previously and
        // all the source locations that eventually embed those source locations.
        MATCH (input_sl)<-[:EMBEDS*0..]-(sl:SourceLocation)
        // Find all the container images that embed an artifact built from any of the source
        // locations
        OPTIONAL MATCH (sl)<-[:BUILT_FROM]-(:Build)-[:PRODUCED]->(:Artifact)<-[:EMBEDS]
            -(with_embedded_artifact:Artifact {{type: 'container'}})
        // Find all the container images that were built from any of the source locations
        OPTIONAL MATCH (sl)<-[:BUILT_FROM]-(:Build {{type: 'container'}})-[:PRODUCED]
            ->(built_from_sl:Artifact {{type: 'container'}})
        // Combine the last two matches and store it in a collection called affected_containers
        WITH COLLECT(with_embedded_artifact) + COLLECT(built_from_sl) AS affected_containers
        // Unwind the collection so that further queries can take place, and make the values unique
        UNWIND affected_containers as affected_container
        WITH DISTINCT affected_container as affected_container
        // Find all the container image builds that produced containers that were built with any of
        // the affected containers
        OPTIONAL MATCH (affected_container)<-[:BUILT_WITH]-(:Artifact {{type: 'container'}})
            <-[:PRODUCED]-(affected_build:Build)
        // Find all the container image builds that embed an artifact that was built with an
        // artifact that was built using the input source locations. This is repeating some of the
        // query above, but the UNWIND cuts the list down so it seems necessary.
        OPTIONAL MATCH (sl)<-[:BUILT_FROM]-(:Build)-[:PRODUCED]->(:Artifact)<-[:BUILT_WITH]
            -(:Artifact)<-[:EMBEDS]-(:Artifact {{type: 'container'}})<-[:PRODUCED]
            -(with_built_with_artifact:Build)
        // Combine the results, which represent all container image builds with artifacts built with
        // artifacts built from the source locations, and the container image builds that were built
        // with container images with artifacts from the source locations
        WITH COLLECT(with_built_with_artifact) + COLLECT(affected_build) as return_values
        // Unwind the collection so duplicates can be removed
        UNWIND return_values AS return_value
        RETURN DISTINCT return_value
    """.format(', '.join(repr(sl['url']) for sl in source_locations if 'url' in sl))
    results, _ = neomodel.db.cypher_query(query)
    return [result[0]['id'] for result in results]
