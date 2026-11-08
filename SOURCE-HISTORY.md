# Source snapshots and GitHub history

Upstream: [https://github.com/vanna-ai/vanna](https://github.com/vanna-ai/vanna) at `365d0617c1a4567ffee1b19b40c27feb4206bfcf`.

The local maintenance history starts from a downloaded upstream source archive. This repository imports those reviewed snapshots after the owner's initial repository commit. GitHub commits are recreated through the connected API, so their commit IDs differ; **all nine imported Git trees were checked to match the local trees exactly**.

| Local source commit | GitHub commit | Matching tree | Change |
|---|---|---|---|
| `a236cc96cc12` | [`a5d83462ce85`](https://github.com/hjt2007323/Vanna/commit/a5d83462ce850f54aa51340fe65fde7536c23370) | `ab80756aaaae` | vendor: unpack vanna at 365d0617c1a4567ffee1b19b40c27feb4206bfcf |
| `95dd9e2c8d59` | [`4093ab7a5f4f`](https://github.com/hjt2007323/Vanna/commit/4093ab7a5f4fd7436186eb1900d659594b0435f0) | `d4de3ffd9646` | fix(sqlite): detect result sets from cursor.description, keep empty columns, commit RETURNING |
| `1a64d98d5ae9` | [`0291db472395`](https://github.com/hjt2007323/Vanna/commit/0291db4723958bf44f2172c15639d919804e03b1) | `37dd67d71c6d` | docs: delivery report, upstream provenance, reproducer, demo and evidence |
| `907d76e2f593` | [`dcfebc661e25`](https://github.com/hjt2007323/Vanna/commit/dcfebc661e2547ef1b27a9040c3facb76e270687) | `3e244c259849` | docs: add artifact manifest (path, size, SHA256) for the delivered tree |
| `e8930554cff6` | [`d845904fbc7e`](https://github.com/hjt2007323/Vanna/commit/d845904fbc7e2fb00aed5ccc5adff32124aa2cb2) | `38a957ed4212` | docs: record R1 acceptance and put the read-only PRAGMA policy in the README |
| `de12f4e04df9` | [`9f2857f5df5a`](https://github.com/hjt2007323/Vanna/commit/9f2857f5df5ae0398b25f6971c38779c5b5ddff9) | `168179d67da0` | docs: refresh artifact manifest after the R1 follow-up (docs only) |
| `d75387cd2cfd` | [`183394621dc5`](https://github.com/hjt2007323/Vanna/commit/183394621dc59bf4a87748eee8cf79fb80871ca4) | `088939a7cc95` | docs: point the delivery report at the r1-accepted tag |
| `e0993a6c0877` | [`c999cb642b34`](https://github.com/hjt2007323/Vanna/commit/c999cb642b34cdb47b0d0c90ddbea114da00e2af) | `c7aeeb30430e` | docs: refresh artifact manifest after the tag note |
| `0a799c4eb721` | [`fe320b9db60f`](https://github.com/hjt2007323/Vanna/commit/fe320b9db60f053ce34fbce341530779c5998ff0) | `e287bbfc0df5` | docs: prepare attributed component portfolio publication |

The owner's initial README and license scaffold remain in the first commit. Current files retain the upstream license texts and applicable path mapping. Component behavior, tests and evidence are described on the main README; the upstream framework is attributed in UPSTREAM.md.

Machine-readable mapping: [SOURCE-HISTORY.json](SOURCE-HISTORY.json).
