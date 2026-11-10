# DBAG Guidance Only

Manual guidance for three groups running in parallel. One host Mac runs the two browser interfaces for each group and saves a separate guidance recap for each session. Each operator and student screen can use a different internet connection.

## Start a pilot

On the **host Mac**, install Python 3.10 or later and Cloudflare's tunnel client. With Homebrew, install the latter once with:

```sh
brew install cloudflared
```

From this repository's folder, run:

```sh
python3 -m guidance
```

The terminal prints two HTTPS links per group. Send the full **Operator** link to that group's operator and the full **Students** link to that group's student Mac. The operator can also copy the student link under **Écran du groupe**. The six remote Macs only need a current browser and internet access. Keep the host Mac awake, online, and running the launcher throughout the session.

| On the operator Mac | On the student Mac |
| --- | --- |
| Open the operator link and check the group number. | Open the student link and check the group number. |
| Type guidance in French. Optionally select a research category and add a private operator note. | Leave the page open. New messages appear automatically, with earlier messages below. |
| Select **Envoyer sans son** or **Envoyer avec notification sonore**. | Select **Activer les notifications sonores** once after opening the page if priority guidance should chime. |

Treat the full links as credentials. Anyone with an operator link can send guidance and view that group's recap. Anyone with a student link can see that group's messages. Links use separate random credentials for every role and group, and expire when the launcher stops. Cloudflare Quick Tunnels are intended for testing and use a new hostname each time. Rehearse from the actual HEP and remote networks before the session. [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

If Cloudflare cannot start a tunnel, check its error in the host terminal. A pre-existing default Cloudflare configuration can interfere with Quick Tunnels.

## Save the recaps

On the host Mac, press **Control+C once** and wait for the three saved paths. Each group has its own folder:

```text
guidance_sessions/group-1/<session-id>/guidance_recap.csv
guidance_sessions/group-2/<session-id>/guidance_recap.csv
guidance_sessions/group-3/<session-id>/guidance_recap.csv
```

Use `--data-dir /path/to/folder` to choose a different destination. Recaps are updated after each send and display confirmation. They include timestamps, message text, the research category, the operator note, whether the send was priority, and browser display confirmation. A confirmation means the browser reported rendering the message while the page was visible.

Every session also saves an `events.jsonl` journal. If a recap needs to be rebuilt, use the actual session folder:

```sh
python3 -m guidance.recovery "guidance_sessions/group-1/YOUR_SESSION_ID"
```

## Rehearse on one Mac

```sh
python3 -m guidance --local
```

Open the local operator and student links for any group on the host Mac. Before using the remote setup with participants, send one example from each operator and confirm it appears on the matching student screen. End the rehearsal and start a new run for the pilot.

The interface, delivery log, CSV export, and journal recovery are adapted from [Dialogue-Based Adaptive Guidance](https://github.com/sophiech05/dialogue-based-adaptive-guidance) at commit `63fc3b5987f4469c24f1d7771ae151060f83b897`. This repository requires only Python's standard library and uses Cloudflare for the remote HTTPS connection.
