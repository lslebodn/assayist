FROM fedora:28

# This is an argument for a URL to an internal CA file to trust
ARG ca_file
# This is an argument for a URL to a DNF repo file of a repo that contains brewkoji
ARG rcm_tools_repo_file
ADD $ca_file /usr/share/pki/ca-trust-source/anchors/custom-ca.crt
ADD $rcm_tools_repo_file /etc/yum.repos.d/rcm-tools-fedora.repo
RUN update-ca-trust

RUN dnf -y install \
  --setopt=deltarpm=0 \
  --setopt=install_weak_deps=false \
  --setopt=tsflags=nodocs \
  # Install brewkoji for the koji.conf.d config file
  brewkoji \
  python3-koji \
  python3-neomodel \
  && dnf clean all

RUN mkdir /src
WORKDIR /src
COPY . .

RUN pip3 install . --no-deps

USER 1001
# TODO: Change this once we have a startup script
CMD ["/bin/bash"]
