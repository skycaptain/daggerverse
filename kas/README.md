# Kas Dagger Module

A [Dagger](https://dagger.io/) module for [kas](https://github.com/siemens/kas), a setup tool for bitbake-based Yocto/OpenEmbedded projects.

This module provides a containerized environment for building Yocto/OpenEmbedded projects using kas, enabling reproducible builds across different development environments. It supports all major kas operations including project setup, building, repository management, and configuration dumping.

Read the documentation at <https://daggerverse.dev/mod/github.com/skycaptain/daggerverse/kas>.

## Usage

Build a Yocto project:

```bash
$ dagger call -m github.com/skycaptain/daggerverse/kas \
    build --src ./my-yocto-project --config kas.yml \
    export --path ./build
```

Checkout repositories for a kas configuration:

```bash
$ dagger call -m github.com/skycaptain/daggerverse/kas \
    checkout --src ./my-yocto-project --config kas.yml \
    export --path ./build
```

Run a shell command in the kas environment:

```bash
$ dagger call -m github.com/skycaptain/daggerverse/kas \
    shell --src ./my-yocto-project --config kas.yml \
    --command "bitbake-layers show-layers" \
    stdout
```

Dump the resolved kas configuration:

```bash
$ dagger call -m github.com/skycaptain/daggerverse/kas \
    dump --src ./my-yocto-project --config kas.yml \
    --format yaml \
    contents
```

Generate a lock file:

```bash
$ dagger call -m github.com/skycaptain/daggerverse/kas \
    lock --src ./my-yocto-project --config kas.yml \
    contents > kas.lock.yml
```

Use a custom kas image:

```bash
$ dagger call -m github.com/skycaptain/daggerverse/kas \
    --base-image-ref artifacts.mycompany.com/my-kas-image:1.2.3 \
    build --src ./my-yocto-project --config kas.yml
```

Build with authentication using a netrc file:

```bash
$ dagger call -m github.com/skycaptain/daggerverse/kas \
    with-netrc --path env:NETRC_SECRET \
    build --src ./my-yocto-project --config kas.yml
```

Run kas commands on all repositories:

```bash
$ dagger call -m github.com/skycaptain/daggerverse/kas \
    for-all-repos --src ./my-yocto-project --config kas.yml \
    --command "git status" \
    stdout
```
