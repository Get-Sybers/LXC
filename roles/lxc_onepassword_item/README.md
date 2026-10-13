# lxc_onepassword_item

The credential-**mirror primitive**: upsert exactly one item into a self-hosted
[1Password Connect](https://developer.1password.com/docs/connect/) vault through one interface — `onepassword.connect.generic_item` — so the
`reflect-onepassword-credentials` play can loop a list of credentials and reflect each into 1Password. It is the write-side counterpart to
`lxc_onepassword_connect`'s build side.

- **Privilege:** none in particular — it is an API client. Runs wherever it can reach the Connect server (the reflect play runs it on the
  controller/node and talks to the Connect LXC over HTTP).
- **Collections:** `onepassword.connect` (plus `ansible.builtin`).
- **Idempotent:** yes. `generic_item` reconciles by title, so a second run with the same inputs reports `changed=0`.
- **Platforms:** Debian (bookworm, trixie). **Min ansible:** 2.19.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `lxc_onepassword_item_host` | Yes | `""` | Connect server base URL, e.g. `http://10.0.0.5:8080`. |
| `lxc_onepassword_item_token` | Yes | `""` | Connect access token (**secret**, from the vault; the role fails fast if empty). |
| `lxc_onepassword_item_vault_id` | Yes | `""` | The 1Password vault id/name the token may write to. |
| `lxc_onepassword_item_validate_certs` | No | `true` | Validate the Connect TLS cert (ignored for `http://`). |
| `lxc_onepassword_item_health_path` | No | `/health` | Readiness path probed before the upsert (`/heartbeat` for pure liveness). |
| `lxc_onepassword_item_title` | Yes | `""` | Item title — the identity `generic_item` reconciles on. |
| `lxc_onepassword_item_category` | No | `api_credential` | Item category (`api_credential`, `password`, `database`, …). |
| `lxc_onepassword_item_fields` | Yes | `[]` | List of `{label, value, field_type, section?}` (**values are secret**). |
| `lxc_onepassword_item_state` | No | `present` | `present` upserts; `absent` removes. |

## Dependencies

None declared. The caller supplies the connection inputs (host/token/vault) and the item; `reflect-onepassword-credentials` reads them from the
vaulted `inventory/secrets/onepassword.yml`.

## Example

```yaml
- name: Reflect one credential into 1Password
  ansible.builtin.include_role:
    name: get_sybers.lxc.lxc_onepassword_item
  vars:
    lxc_onepassword_item_host: "http://10.0.0.5:8080"
    lxc_onepassword_item_token: "{{ vault_onepassword_connect_token }}"
    lxc_onepassword_item_vault_id: "abcdefghijklmnop"
    lxc_onepassword_item_title: "Ludus RA API key"
    lxc_onepassword_item_fields:
      - { label: credential, field_type: concealed, value: "RA.…" }
```

## Behaviour

Asserts the inputs, probes `{{ host }}{{ health_path }}` with `failed_when: false` and asserts a healthy `200` (an unreachable server becomes a
labelled diagnostic, never a raw `uri` crash), then calls `generic_item`. Every secret-bearing task is `no_log`; the final debug reports only the
item title and field **count**, never any value.
