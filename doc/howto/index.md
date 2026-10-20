# How-to guides

Step-by-step guides for the operations this collection is used for.

| Guide | When |
| --- | --- |
| [Deploy 1Password Connect](deploy-onepassword-connect.md) | Stand up the Connect server in a hardened container and mirror the lab's credentials into it. |
| [Deploy Semaphore UI](deploy-semaphore.md) | Stand up Semaphore UI (the web UI and API for Ansible) in a hardened container, on SQLite, from the official package. |
| [Deploy distrobuilder](deploy-distrobuilder.md) | Stand up the distrobuilder build box in a hardened container and build LXC images from reviewed definitions on the cluster. |
| [Deploy Velociraptor](deploy-velociraptor.md) | Stand up the Velociraptor DFIR server in a hardened container and collect from endpoints across the lab. |
| [Deploy GHOSTS (ghost9)](deploy-ghost9.md) | Stand up the GHOSTS NPC/user-simulation server (API, UI, n8n, Grafana) as native services in a hardened container. |
| [Build and release a template](build-a-template.md) | How a template is baked, published to GHCR as an OCI image, imported onto a node with Proxmox's OCI support, verified, and how a base template is raised. |
| [Add a service](add-a-service.md) | What a new service needs: a template, a role with the four entry points, a play, a placement file, a scenario. |
