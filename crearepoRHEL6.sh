#!/bin/bash

/usr/bin/createrepo -g /var/lib/pulp/repos/redhat6/$1/comps.xml /var/lib/pulp/repos/redhat6/$1/
/bin/cp /var/cache/yum/x86_64/6Server/$1/gen/updateinfo.xml /var/lib/pulp/repos/redhat6/$1/repodata/
/usr/bin/modifyrepo /var/lib/pulp/repos/redhat6/$1/repodata/updateinfo.xml /var/lib/pulp/repos/redhat6/$1/repodata/

