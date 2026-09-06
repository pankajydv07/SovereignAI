# Security Model

## What we defend against, and what we do not

Stating the boundary honestly is a strength. A blanket claim of "it's sandboxed and secure" invites the one question that unravels a demo.

| Threat | Defence |
|---|---|
| Prompt injection in an ingested document attempting exfiltration | No egress tool exists in the registry; kernel-level default-deny; every write is gated |
| Prompt injection attempting tool escalation | Tools are declared with schemas and side-effect classes; the policy engine, not the model, decides permission |
| Model-generated code reaching the network | Sandbox has **no network interface** — not blocked, absent |
| Model-generated code reaching the host filesystem | Read-only rootfs, workspace bind only, seccomp allowlist, resource caps |
| Path traversal out of the workspace | Single canonicalising resolver with explicit negative tests |
| A user retrieving documents above their clearance | Retrieval filtered in the data layer before rows are returned |
| Tampering with the audit trail | Append-only, hash-chained; each record embeds the previous record's hash |
| A dependency introducing egress | CI sovereignty grep; per-commit checklist; vendored assets |

**Not defended against:** a privileged host administrator. That is correctly an organisational control, and we say so rather than implying otherwise.

## The four egress layers

Defence in depth — any single layer failing does not produce egress.

1. **Kernel / netfilter.** `nftables` OUTPUT policy `drop`; accept only the internal subnet, internal DNS and loopback, applied per-cgroup so the app plane cannot reach a default route even if one exists.
2. **Network namespace.** App and inference containers sit on an internal-only bridge with **no default gateway configured**. There is no route to attempt.
3. **Sandbox.** `--unshare-net` / `network_mode: none` — no interface at all.
4. **Application.** No HTTP client configured with an external base URL; no `web_search` or fetch tool in the registry; proxy environment variables scrubbed; model paths pinned local.

## Proof, not assertion

An eBPF probe on `tcp_connect` and `udp_sendmsg` captures every outbound attempt — allowed or dropped — with pid, process name, cgroup, destination and verdict. This feeds the Sovereignty panel and the audit store.

**Detection matters as much as blocking.** An undetected block is not evidence. The deliberate-attempt test in `/sovereignty-audit` verifies both.

If the eBPF probe is not attached, the UI must **not** show green. It shows `--verify`: *"Egress monitoring inactive — enforcement is active but unverified."* Claiming zero egress without a live monitor would be dishonest, and the UI refuses to do it.

| Control | bubblewrap (Linux) | AppContainer + JobObject (Windows) | Container | gVisor | Firecracker |
|---|---|---|---|---|---|
| Network | No interface (`--unshare-net`) | Kernel capability denial (`WSAEACCES`, 0 capabilities) | `--network=none` | No interface | No NIC attached |
| Kernel isolation | Namespaces (`--unshare-ipc/uts/pid/cgroup`, `--cap-drop ALL`, `--new-session`) | AppContainer SID ACLs + JobObject limits (2GB job RAM, 16 procs, CPU cap) | Namespaces | Syscall interposition | Hardware VM |
| Overhead | Minimal | Minimal | Minimal | 10–30% on I/O | ~100ms boot |
| Extra dependency | None | None (native Win32) | Runtime required | runsc | KVM |

**Windows Architecture vs. Linux Architecture:**
- **Linux (`bubblewrap`):** Unshares the network namespace completely — no network interfaces exist inside the container except isolated loopback.
- **Windows (`AppContainer`):** OS network interfaces remain visible to the subsystem, but kernel security checks deny socket creation and DNS requests (`WSAEACCES`, Error 10013) because the process token has zero network capabilities (`internetClient` and `privateNetworkClientServer` omitted). Loopback access to local services like Ollama (127.0.0.1:11434) is blocked without `LoopbackExempt`.

## Supply chain

Safetensors only, SHA-256 verified against a signed manifest before load. `trust_remote_code=False` in production — any custom modelling code is vendored and reviewed. No pickle-format checkpoints. Weights served from a local store, never fetched at runtime.

Dependencies: permissive licences only. Model licences surfaced in the UI, with non-commercial weights marked undeployable.

## Air-gapped update procedure

Internal mirrors for images, Python packages, OS packages and weights. Updates arrive as a **signed offline bundle** on removable media: checksum and signature verified, staged into a quarantine namespace, benchmarked by the eval harness, promoted only on pass. Bundle contents, operator identity and the promotion decision all enter the audit chain.

## Audit chain

Append-only. Each record contains: run id, user, prompt, plan, every step with tool and duration, documents retrieved with classification, models used, deliverables produced, the approval event with approver identity and any edits, plus `prev_hash` and `record_hash`.

Chain verification is a first-class UI action. **Design the failure state first** — a tamper-evident log whose interface cannot show tampering is pointless. On a break, the header turns critical and names the exact record index where verification failed.

Exports are themselves audited. An audit system with an unaudited export path has a hole in it.
