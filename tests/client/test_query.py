# SPDX-License-Identifier: GPL-3.0+

from assayist.client import query
from assayist.common.models.content import Build, Artifact
from assayist.common.models.source import SourceLocation, Component


def test_get_container_sources():
    """Test the get_container_sources function."""
    # Create the container build entry
    container_build_id = '742663'
    container_build = Build(id_=container_build_id, type_='container').save()
    container_filename = ('docker-image-sha256:98217b7c89052267e1ed02a41217c2e03577b96125e923e9594'
                          '1ac010f209ee6.x86_64.tar.gz')
    container_artifact = Artifact(
        archive_id='742663',
        architecture='x86_64',
        filename=container_filename,
        type_='container').save()
    container_build.artifacts.connect(container_artifact)
    container_internal_url = ('git://pks.domain.local/containers/etcd#'
                              '3dcd6fc75e674589ac7d2294dbf79bd8ebd459fb')
    container_internal_source = SourceLocation(url=container_internal_url).save()
    container_build.source_location.connect(container_internal_source)

    # Create the embedded artifacts
    etcd_build = Build(id_='770188', type_='rpm').save()
    etcd_rpm = Artifact(
        archive_id='5818103',
        architecture='x86_64',
        filename='etcd-3.2.22-1.el7.x86_64.rpm',
        type_='rpm').save()
    etcd_build.artifacts.connect(etcd_rpm)
    etcd_upstream_url = ('https://github.com/coreos/etcd/archive/1674e682fe9fbecd66e9f20b77da852ad7'
                         'f517a9/etcd-1674e682.tar.gz')
    etcd_upstream_source = SourceLocation(url=etcd_upstream_url).save()
    etcd_internal_url = 'git://pks.domain.local/rpms/etcd#84858fb38a89e1177b0303c675d206f90f6a83e2'
    etcd_internal_source = SourceLocation(url=etcd_internal_url).save()
    etcd_build.source_location.connect(etcd_internal_source)
    etcd_internal_source.upstream.connect(etcd_upstream_source)
    container_artifact.embedded_artifacts.connect(etcd_rpm)

    yum_utils_build = Build(id_='728353', type_='rpm').save()
    yum_utils_rpm = Artifact(
        archive_id='5962202',
        architecture='x86_64',
        type_='rpm',
        filename='yum-utils-1.1.31-46.el7_5.noarch.rpm').save()
    yum_utils_build.artifacts.connect(yum_utils_rpm)
    yum_utils_upstream_url = 'http://yum.baseurl.org/download/yum-utils/yum-utils-1.1.31.tar.gz'
    yum_utils_upstream_source = SourceLocation(url=yum_utils_upstream_url).save()
    yum_utils_internal_url = ('git://pks.domain.local/rpms/yum-utils#562e476db1be88f58662d6eb3'
                              '82bb37e87bf5824')
    yum_utils_internal_source = SourceLocation(url=yum_utils_internal_url).save()
    yum_utils_build.source_location.connect(yum_utils_internal_source)
    yum_utils_internal_source.upstream.connect(yum_utils_upstream_source)
    container_artifact.embedded_artifacts.connect(yum_utils_rpm)

    expected = {
        'internal_urls': [yum_utils_internal_url, etcd_internal_url],
        'upstream_urls': [yum_utils_upstream_url, etcd_upstream_url]
    }
    assert query.get_container_content_sources(container_build_id) == expected


def test_get_current_and_previous_versions():
    """Test the get_current_and_previous_versions function."""
    go = Component(
        canonical_name='golang', canonical_type='generic', canonical_namespace='redhat').save()
    next_sl = None
    url = 'git://pkgs.domain.local/rpms/golang?#fed96461b05c0078e537c93a3fe974e8b334{version}'
    for version in ('1.9.7', '1.9.6', '1.9.5', '1.9.4', '1.9.3'):
        sl = SourceLocation(
            url=url.format(version=version.replace('.', '')), canonical_version=version).save()
        sl.component.connect(go)
        if next_sl:
            next_sl.previous_version.connect(sl)
        next_sl = sl

    rv = query.get_current_and_previous_versions('golang', 'generic', '1.9.6')
    versions = set([result['canonical_version'] for result in rv])
    assert versions == set(['1.9.6', '1.9.5', '1.9.4', '1.9.3'])


def test_get_container_built_with_artifact():
    """
    Test the test_get_container_built_with_artifact function.

    This test data creates a scenario where there are container builds with vulnerable golang
    RPMs embedded, that are used during multi-stage builds. There is also a container with the
    prometheus RPM embedded, but the prometheus RPM was built with a vulnerable version of the
    golang RPMs.
    """
    expected = set()
    api_input = []
    queried_sl_versions = {'1.9.6', '1.9.5', '1.9.3'}
    go = Component(
        canonical_name='golang', canonical_type='generic', canonical_namespace='redhat').save()

    artifact_counter = 0
    build_counter = 0
    next_sl = None
    url = 'git://pkgs.domain.local/rpms/golang?#fed96461b05c0078e537c93a3fe974e8b334{version}'

    for version in ('1.9.7', '1.9.6', '1.9.5', '1.9.4', '1.9.3'):
        sl = SourceLocation(
            url=url.format(version=version.replace('.', '')), canonical_version=version).save()
        sl.component.connect(go)
        if next_sl:
            next_sl.previous_version.connect(sl)
        if version in queried_sl_versions:
            api_input.append({'url': sl.url})
        go_build = Build(id_=build_counter, type_='rpm').save()
        go_build.source_location.connect(sl)
        build_counter += 1

        go_src_rpm_artifact = Artifact(archive_id=artifact_counter, type_='rpm', architecture='src',
                                       filename=f'golang-{version}-1.el7.src.rpm').save()
        go_src_rpm_artifact.build.connect(go_build)
        artifact_counter += 1

        # Don't create container builds for version 1.9.3 because it'll be used by prometheus below
        # to test another part of the query
        if version != '1.9.3':
            go_container_build = Build(id_=build_counter, type_='container').save()
            build_counter += 1

            content_container_build = Build(id_=build_counter, type_='container').save()
            if version in queried_sl_versions:
                # All the content containers are built with a container with a vulnerable golang
                # RPM, but since we only query for certain source location versions of golang, only
                # add those we are searching for.
                expected.add(str(content_container_build.id_))
            build_counter += 1

        for noarch_rpm in ('docs', 'misc', 'src', 'tests'):
            go_noarch_artifact = Artifact(
                archive_id=artifact_counter, type_='rpm', architecture='noarch',
                filename=f'golang-{noarch_rpm}-{version}-1.el7.noarch.rpm').save()
            go_noarch_artifact.build.connect(go_build)
            artifact_counter += 1

        for arch in ('aarch64', 'x86_64', 'ppc64le', 's390x'):
            go_artifact = Artifact(archive_id=artifact_counter, type_='rpm', architecture=arch,
                                   filename=f'golang-{version}-1.el7.{arch}.rpm').save()
            go_artifact.build.connect(go_build)
            artifact_counter += 1
            gobin_artifact = Artifact(archive_id=artifact_counter, type_='rpm', architecture=arch,
                                      filename=f'golang-bin-{version}-1.el7.{arch}.rpm').save()
            gobin_artifact.build.connect(go_build)
            artifact_counter += 1

            if version != '1.9.3':
                go_container_build_artifact = Artifact(
                    archive_id=artifact_counter, type_='container', architecture=arch).save()
                go_container_build_artifact.build.connect(go_container_build)
                go_container_build_artifact.embedded_artifacts.connect(go_artifact)
                go_container_build_artifact.embedded_artifacts.connect(gobin_artifact)
                artifact_counter += 1

                content_container_artifact = Artifact(
                    archive_id=artifact_counter, type_='container', architecture=arch).save()
                content_container_artifact.build.connect(content_container_build)
                content_container_artifact.buildroot_artifacts.connect(go_container_build_artifact)
                artifact_counter += 1

        next_sl = sl

    prometheus = Component(
        canonical_name='prometheus', canonical_type='generic', canonical_namespace='redhat').save()
    prometheus_url = ('git://pkgs.domain.local/rpms/golang-github-prometheus-prometheus?#41d8a98364'
                      'a9c631c7f663bbda8942cb2741df49')
    prometheus_sl = SourceLocation(url=prometheus_url, canonical_version='2.1.0').save()
    prometheus_sl.component.connect(prometheus)
    prometheus_build = Build(id_=build_counter, type_='rpm').save()
    prometheus_build.source_location.connect(prometheus_sl)
    build_counter += 1
    prometheus_src_rpm_artifact = Artifact(
        archive_id=artifact_counter, type_='rpm', architecture='src',
        filename='golang-github-prometheus-prometheus-2.2.1-1.gitbc6058c.el7.src.rpm').save()
    prometheus_src_rpm_artifact.build.connect(go_build)
    artifact_counter += 1
    prometheus_container_build = Build(id_=build_counter, type_='container').save()
    # This prometheus container will embed a prometheus RPM that was built with a vulnerable golang
    # RPM, and 1.9.3 is part of the query
    expected.add(str(prometheus_container_build.id_))
    build_counter += 1

    for arch in ('x86_64', 's390x', 'ppc64le'):
        prometheus_artifact = Artifact(
            archive_id=artifact_counter, type_='rpm', architecture=arch,
            filename=f'prometheus-2.2.1-1.gitbc6058c.el7.{arch}.rpm').save()
        prometheus_artifact.build.connect(prometheus_build)
        # Set the 1.9.3 go artifacts to be buildroot artifacts
        go_artifact = Artifact.nodes.get(filename=f'golang-1.9.3-1.el7.{arch}.rpm')
        prometheus_artifact.buildroot_artifacts.connect(go_artifact)
        gobin_artifact = Artifact.nodes.get(filename=f'golang-bin-1.9.3-1.el7.{arch}.rpm')
        prometheus_artifact.buildroot_artifacts.connect(gobin_artifact)
        artifact_counter += 1
        prometheus_container_artifact = Artifact(
            archive_id=artifact_counter, type_='container', architecture=arch).save()
        prometheus_container_artifact.build.connect(prometheus_container_build)
        prometheus_container_artifact.embedded_artifacts.connect(prometheus_artifact)
        artifact_counter += 1

    rv = query.get_container_built_with_sources(api_input)

    assert set(rv) == expected
