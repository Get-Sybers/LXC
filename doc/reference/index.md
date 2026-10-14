# Reference

Technical information: the rules, the formats, the contracts.

| Reference | What it specifies |
| --- | --- |
| [The hardened-LXC premise](hardened-lxc-premise.md) | The nine rules every container is held to, and the role, task file or script that enforces each. |
| [Template manifest](template-manifest.md) | The keys of `templates/<name>/template.yml`, the bake environment, and what a bake adds to the rootfs. |
| [`lxc_guest`](../../roles/lxc_guest/README.md) | The one lifecycle: entry points, what preflight refuses, inputs. |
| [`lxc_preflight`](../../roles/lxc_preflight/README.md) | The node admission gate. |
| [`lxc_onepassword_connect`](../../roles/lxc_onepassword_connect/README.md) | The Connect build (`bake`) and runtime (`server`) contract. |
| [`lxc_onepassword_item`](../../roles/lxc_onepassword_item/README.md) | The Connect API client. |
| [`lxc_semaphore`](../../roles/lxc_semaphore/README.md) | The Semaphore UI build (`bake`) and runtime (`server`) contract. |
| [`lxc_distrobuilder`](../../roles/lxc_distrobuilder/README.md) | The distrobuilder build-box build (`bake`), runtime (`server`) and interaction (`build`) contract. |
| [Inventory](../../inventory/README.md) | The single config home: groups, collection variables, placement files, secrets. |
