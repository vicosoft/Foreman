#!/usr/bin/env python3
# -*- coding: utf-8 -*-


# The MIT License (MIT)
#
# Copyright (C) 2018 Kungliga Tekniska högskolan
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.


import sys
import subprocess
import json
import shlex
from functools import reduce
import argparse
import datetime




def union_of_all(*sets):
    def union_of_a_and_b(a, b):
        return a.union(b)
    return reduce(union_of_a_and_b, sets, set())




global_variables = {
    "verbose_level": 0,
    "allow_updates": True
}


def set_verbose(verbose):
    global_variables["verbose_level"] = verbose


def set_dry_run():
    global_variables["allow_updates"] = False


def verbose_print(levels, *args, **kwargs):
    if global_variables["verbose_level"] in levels:
        print(*args, **kwargs)


def hammer(*args, updates=True):
    commandline = ["hammer"] + ("--verbose" if global_variables["verbose_level"] in [2] else []) + ["--output", "json"]+ list(args)
    commandlinestring = " ".join([shlex.quote(str(s)) for s in commandline])


    if updates and not global_variables["allow_updates"]:
        raise Exception("Aborting before execution of command line: %s" % (commandlinestring))


    verbose_print([1,2], "Execute commandline%s: %s" % (" (updates)" if updates else "", commandlinestring), file=sys.stderr)


    for arg in args:
        assert(arg is not None)
        assert(isinstance(arg, str))


    completed = subprocess.run(commandline, stdout=subprocess.PIPE)
    # (Modify completed.args here if secrets were sent on the commandline.)
    completed.check_returncode()


    jsondata = completed.stdout.decode("utf8")
    if len(jsondata) > 0:
        verbose_print([2], "Command result:\n%s" % (jsondata), file=sys.stderr)
        verbose_print([1], "Command successful, returned JSON data.", file=sys.stderr)
        return json.loads(jsondata)
    verbose_print([1,2], "Command successful, returned no data.", file=sys.stderr)
    return None






# Fail if not currently authenticated.
#  This does not ensure that the session is still valid (not expired).
def ensure_auth_session():
    authstatus = hammer("auth", "status", updates=False)
    if 'message' not in authstatus or 'Session exists' not in authstatus['message']:
        raise Exception("Login required: hammer auth login --help")




# Get all data about a content view.
#  the view must match the view id
def get_lifecycle_environment_data():
    return hammer("lifecycle-environment", "list", "--organization-id", "1", updates=False)


def get_promotion_path(promote_to_environment, promote_from_environment=None):
    envs = get_lifecycle_environment_data()
    def find_env(name):
        for env in envs:
            if env["Name"] == name:
                return env
        if promote_from_environment:
            raise Exception("No promotion path exists from %s to %s" % (promote_from_environment, promote_to_environment))
        raise Exception("No promotion path exists to %s" % (promote_to_environment))
    if promote_from_environment:
        # Ensure it exists.
        find_env(promote_from_environment)
    def walk(startenv, stopenv):
        if startenv == stopenv:
            return []
        env = find_env(stopenv)
        if env["Prior"] is None:
            return []
        return walk(startenv, env["Prior"]) + [(env["Prior"], env["Name"])]
    path = walk(promote_from_environment, promote_to_environment)


    pathdesc = [path[0][0]] + [t for (f,t) in path]
    if promote_from_environment:
        verbose_print([1,2], "Path from %s to %s: %s" % (promote_from_environment, promote_to_environment, " - ".join(pathdesc)), file=sys.stderr)
    else:
        verbose_print([1,2], "Path to %s: %s" % (promote_to_environment, " - ".join(pathdesc)), file=sys.stderr)


    return path


def get_promotion_paths(promote_to_environments, **kwargs):
    return [get_promotion_path(promote_to_environment, **kwargs) for promote_to_environment in promote_to_environments]


#  the view must match the view id
def get_content_view_description(content_view_name, content_view_id):
    if content_view_id is None:
        content_view_info = hammer("content-view", "info", "--organization-id", "1", "--name", content_view_name, updates=False)
    else:
        content_view_info = hammer("content-view", "info", "--organization-id", "1", "--name", content_view_name, "--id", str(content_view_id), updates=False)
    return content_view_info['Description']


#  the view must match the view id
def get_composite_view_component_versions(composite_view_name, composite_view_id):
    composite_view_info = hammer("content-view", "info", "--organization-id", "1", "--name", composite_view_name, "--id", str(composite_view_id), updates=False)
    composite_view_component_versions = composite_view_info['Components'].values()
    # composite_view_component_versions will be a list of { "ID": 193, "Name": "misc-el7 9.0" }
    return [(component["Name"].rsplit(" ", 1)[0], component["ID"]) for component in composite_view_component_versions]


#  the view must match the view id
def get_composite_view_components(composite_view_name, composite_view_id):
    composite_view_info = hammer("content-view", "info", "--organization-id", "1", "--name", composite_view_name, "--id", str(composite_view_id), updates=False)
    composite_view_component_versions = composite_view_info['Components'].values()
    # composite_view_component_versions will be a list of { "ID": 193, "Name": "misc-el7 9.0" }
    composite_view_components = [(composite_view_component_version["Name"].rsplit(" ", 1)[0], None) for composite_view_component_version in composite_view_component_versions]
    # composite_view_components will be a list of "misc-el7" etc.
    return set(composite_view_components)


def get_all_composite_view_data(composite_view_names):
    data = hammer("content-view", "list", "--organization-id", "1", "--composite", "true", updates=False)
    for composite_view in data:
        assert(composite_view['Composite'])
    if composite_view_names:
        have_names = set([composite_view['Name'] for composite_view in data])
        for name in composite_view_names:
            if name not in have_names:
                raise Exception("%s does not match any composite view" % (name))
        return [composite_view for composite_view in data if composite_view['Name'] in composite_view_names]
    return data


def get_all_composite_views(composite_view_names):
    composite_view_and_view_ids = [(composite_view['Name'], composite_view['Content View ID']) for composite_view in get_all_composite_view_data(composite_view_names)]
    return composite_view_and_view_ids


# Find all component views which are in a composite view.
def get_all_composite_view_components(composite_view_names):
    all_composite_views = get_all_composite_views(composite_view_names)
    components_sets_for_all_composite_views = [get_composite_view_components(composite_view_name, composite_view_id) for (composite_view_name, composite_view_id) in all_composite_views]
    all_composite_view_components = union_of_all(*components_sets_for_all_composite_views)
    verbose_print([1,2], "All composite view components: %s" % str(all_composite_view_components), file=sys.stderr)
    return all_composite_view_components


# Get all data about a content view.
#  the view must match the view id
def get_content_view_data(content_view_name, content_view_id):
    if content_view_id is None:
        return hammer("content-view", "version", "list", "--organization-id", "1", "--content-view", content_view_name, updates=False)
    else:
        return hammer("content-view", "version", "list", "--organization-id", "1", "--content-view", content_view_name, "--content-view-id", str(content_view_id), updates=False)


# Given a conent view name and id, returns a list of content view versions, sorted by the given key.
#  the view must match the view id
def get_sorted_content_view_data(*args, key='version'):
    def version_key(content_view_version_info):
        version = content_view_version_info['Version']
        return [int(part) for part in version.split(".")]
    keyfuns = {
        'version': version_key
    }
    data = get_content_view_data(*args)
    data.sort(key=keyfuns[key])
    return data


# Given a content view name and id, returns the most current content view version.
#  the view must match the view id
def get_latest_view_version(content_view_name, content_view_id):
    for content_view_version_info in get_content_view_data(content_view_name, content_view_id):
        content_view_version_lifecycle_environments = content_view_version_info['Lifecycle Environments']
        if 'Library' in content_view_version_lifecycle_environments:
            content_view_version = content_view_version_info['Version']
            content_view_version_id = content_view_version_info['ID']
            return (content_view_name, content_view_version_id)
    return None


# content_views is a an iterable of (content_view_name, content_view_id)
#  the view must match the view id
def get_latest_view_versions(content_views):
    return [get_latest_view_version(content_view_name, content_view_id) for (content_view_name, content_view_id) in content_views]






def remove_composite_view_component_version(composite_view_id, component_view_version_id):
    res = hammer("content-view", "remove-version", "--id", str(composite_view_id), "--content-view-version-id", str(component_view_version_id))


def add_composite_view_component_version(composite_view_id, component_view_version_id):
    res = hammer("content-view", "add-version", "--id", str(composite_view_id), "--content-view-version-id", str(component_view_version_id))


def update_composite_view_component_version(composite_view_id, configured_component_version_id, latest_component_version_id):
    verbose_print([1,2], "For composite view %s, update from %s to %s." % (composite_view_id, configured_component_version_id, latest_component_version_id), file=sys.stderr)
    remove_composite_view_component_version(composite_view_id, configured_component_version_id)
    add_composite_view_component_version(composite_view_id, latest_component_version_id)


#  the view must match the view id
def update_composite_view_component_versions(composite_view_name, composite_view_id, latest_component_versions):
    configured_component_versions = get_composite_view_component_versions(composite_view_name, composite_view_id)


    for (latest_component_view_name, latest_component_version_id) in latest_component_versions:
        for (configured_component_view_name, configured_component_version_id) in configured_component_versions:
            if latest_component_view_name == configured_component_view_name:
                if latest_component_version_id != configured_component_version_id:
                    update_composite_view_component_version(composite_view_id, configured_component_version_id, latest_component_version_id)


# composite_views is a an iterable of (content_view_name, content_view_id)
#  the view must match the view id
def update_composite_views_component_versions(composite_views, latest_component_versions):
    for (content_view_name, content_view_id) in composite_views:
        update_composite_view_component_versions(content_view_name, content_view_id, latest_component_versions)


# Deletes a content view version.
#  May raise a subprocess.CalledProcessError on failure.
def delete_content_view_version(content_view_name, content_view_id, content_view_version):
    if content_view_id is None:
        hammer("content-view", "version", "delete", "--organization-id", "1", "--content-view", content_view_name, "--id", str(content_view_version['ID']), "--version", content_view_version['Version'])
    else:
        hammer("content-view", "version", "delete", "--organization-id", "1", "--content-view", content_view_name, "--content-view-id", str(content_view_id), "--id", str(content_view_version['ID']), "--version", content_view_version['Version'])


# Promote a content view from one environment to the next.
#  fromenv must be the prior env of toenv
#  the view name must match the view id
#  the view must match the view id
def promote_content_view_environment(content_view_name, content_view_id, fromenv, toenv, description, force_regen=False):
    for content_view_version in get_content_view_data(content_view_name, content_view_id):
        content_view_version_lifecycle_environments = content_view_version['Lifecycle Environments']
        if fromenv in content_view_version_lifecycle_environments:
            if toenv not in content_view_version_lifecycle_environments:
                # Promote this version.
                hammer("content-view", "version", "promote", "--organization-id", "1", "--content-view", content_view_name, "--content-view-id", str(content_view_id), "--from-lifecycle-environment", fromenv, "--to-lifecycle-environment", toenv, "--description", description, *(["--force-yum-metadata-regeneration", "true"] if force_regen else []))
                return


# Promote a set of content views to <toenv>, if the content view is in <fromenv>.
# content_views is a an iterable of (content_view_name, content_view_id)
#  content_view_name must match content_view_id
def promote_content_views_environment(content_views, fromenv, toenv, description, **kwargs):
    for (content_view_name, content_view_id) in content_views:
        promote_content_view_environment(content_view_name, content_view_id, fromenv, toenv, description, **kwargs)


# Promote a set of content views along the specified path.
# content_views is a an iterable of (content_view_name, content_view_id)
#  content_view_name must match content_view_id
# promotion_path is a list of (from,to) pairs of environment names.
def promote_views_along_path(content_views, promotion_path, description, **kwargs):
    for (promote_from, promote_to) in promotion_path:
        promote_content_views_environment(content_views, promote_from, promote_to, description, **kwargs)


# Promote a set of content views along the paths specified.
# content_views is a an iterable of (content_view_name, content_view_id)
#  content_view_name must match content_view_id
# promotion_paths is a list of lists of (from,to) pairs of environment names.
def promote_views_along_paths(content_views, promotion_paths, description, **kwargs):
    for promotion_path in promotion_paths:
        promote_views_along_path(content_views, promotion_path, description, **kwargs)


#  the view must match the view id
def update_view(content_view_name, content_view_id, description):
    desc = get_content_view_description(content_view_name, content_view_id)
    if desc is not None and ":noautoupdate:" in desc:
        return
    if content_view_id is None:
        hammer("content-view", "publish", "--organization-id", "1", "--name", content_view_name, "--description", description)
    else:
        hammer("content-view", "publish", "--organization-id", "1", "--name", content_view_name, "--id", str(content_view_id), "--description", description)


# content_views is a an iterable of (content_view_name, content_view_id)
#  the view must match the view id
def update_views(content_views, description):
    for (content_view_name, content_view_id) in content_views:
        update_view(content_view_name, content_view_id, description)






# Update composite views and optionally promote to an environment (typically the staging environment).
#  - Update the component views.
#  - Change the component view versions in the composite views.
#  - Update the composite views.
#  - Optionally promote the composite views to the specified environments.
def cmd_update(args):
    ensure_auth_session()


    # Look at promotion parts first, to validate the command line arguments early.
    promotion_paths = get_promotion_paths(args.promote_to) if args.promote_to else []


    # Update the component views.
    components_to_update = get_all_composite_view_components(args.composite_view_names)
    update_views(components_to_update, args.description)
    latest_component_versions = get_latest_view_versions(components_to_update)


    all_composite_views = get_all_composite_views(args.composite_view_names)


    # Change the component view versions in the composite views.
    update_composite_views_component_versions(all_composite_views, latest_component_versions)


    # Update the composite views.
    update_views(all_composite_views, args.description)


    promote_views_along_paths(all_composite_views, promotion_paths, args.description, force_regen=args.force_regen)


# Promote all composite views (typically from the staging environment to production).
def cmd_promote(args):
    ensure_auth_session()


    promotion_paths = get_promotion_paths(args.promote_to, promote_from_environment=args.promote_from)
    all_composite_views = get_all_composite_views(args.composite_view_names)
    promote_views_along_paths(all_composite_views, promotion_paths, args.description, force_regen=args.force_regen)


# Expire content views.
def cmd_expire(args):
    keep = int(args.keep)


    ensure_auth_session()


    all_composite_views = get_all_composite_views(args.composite_view_names)
    components_to_expire = list(get_all_composite_view_components(args.composite_view_names))


    # Expire composite views first, then their components.
    for (content_view_name, content_view_id) in all_composite_views + components_to_expire:
        versions = get_sorted_content_view_data(content_view_name, content_view_id, key='version')
        try_expire = versions[0:-keep]
        for version in try_expire:
            try:
                delete_content_view_version(content_view_name, content_view_id, version)
            except subprocess.CalledProcessError as e:
                verbose_print([1,2], "Ignoring error while deleting content view {} (id {}) version {}: {}".format(content_view_name, content_view_id, version, e), file=sys.stderr)
                verbose_print([0,1,2], "Skipped content view {} (id {}) version {}".format(content_view_name, content_view_id, version))


def main():
    date_and_time = datetime.datetime.now().strftime("%Y%m%d-%H%M")


    longtext = """
Typical usage:


  To update the staging environment:
    %(prog)s -v update --promote-to Staging


  To promote previously staged changes to the production environment:
    %(prog)s -v promote --from Staging --to Production
"""


    parser = argparse.ArgumentParser(description='Manage updates of content views in Foreman/Katello.', epilog=longtext, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--description', default=date_and_time, metavar="STRING", help='set comment added to update operations')
    parser.add_argument('--composite-view', metavar="NAME", action='append', dest="composite_view_names", help='only update/promote this composite view (multiple allowed)')
    parser.add_argument('--dry-run', action='store_true', help='stop before any action which changes existing data')
    parser.add_argument('--verbose', '-v', action='count', help='give more information during operations')
    parser.add_argument('--force-yum-metadata-regeneration', dest="force_regen", action='store_true', help='force metadata regeneration')


    def cmd_help(args):
        parser.print_help()
    parser.set_defaults(func=cmd_help)


    subparsers = parser.add_subparsers(help='sub-command help')


    parser_update = subparsers.add_parser('update', help='update content views')
    parser_update.add_argument('--promote-to', metavar="ENV", action='append', help='also promote the updates directly (multiple allowed)')
    parser_update.set_defaults(func=cmd_update)


    parser_promote = subparsers.add_parser('promote', help='promote content view versions')
    parser_promote.add_argument('--from', dest="promote_from", metavar="ENV", required=True, help='promote from this environment')
    parser_promote.add_argument('--to', dest="promote_to", metavar="ENV", required=True, action='append', help='promote to this environment (multiple allowed)')
    parser_promote.set_defaults(func=cmd_promote)


    parser_expire = subparsers.add_parser('expire', help='expire content view versions')
    parser_expire.add_argument('--keep', metavar="INTEGER", default="12", required=True, help='keep at least the INTEGER latest versions in each ontent view')
    parser_expire.set_defaults(func=cmd_expire)


    args = parser.parse_args()
    set_verbose(args.verbose)
    if args.dry_run:
        set_dry_run()
    args.func(args)


main()
