# Putting Word Spot online at play.silautron.com

This guide puts the Word Spot online game on a small Hetzner cloud server,
so the children can play from any iPad, phone or computer, anywhere. It takes
about 15–20 minutes. You only paste things in; there is no programming.

**What you end up with**

* The game at **https://play.silautron.com**, with the padlock (HTTPS).
* A **family code**: only people who know it can start games. Friends can
  still join a game with its 4-letter code.
* Security updates that install themselves (the server restarts at 04:30
  if an update needs it).
* New versions of Word Spot from GitHub, installed automatically every night
  at 03:30.
* Your existing website, silautron.com, carries on as it is.

**Cost:** about €4–5 a month for the smallest server, plus 20% if you turn on
backups (recommended). Hetzner shows the exact monthly price before you buy.
It's a fixed price, so a busy month can't run up a bill.

---

## Part 1: Create a Hetzner account (5 minutes)

1. Go to **https://www.hetzner.com/cloud** and click **Sign up** (or *Register*).
2. Enter your email, confirm it, and fill in your details and payment method
   (card or PayPal). Hetzner sometimes asks for ID verification for new
   accounts. If so, follow its steps, which can take a few hours.
3. Once in the **Cloud Console**, click **+ New project**, call it `Home`,
   and open it.

## Part 2: Create the server (5 minutes)

1. Inside the project, click **Add Server** (or **Create Server**).
2. **Location:** any one is fine (Nuremberg, Falkenstein or Helsinki).
3. **Image:** **Ubuntu 24.04**.
4. **Type:** *Shared vCPU*, then the **cheapest** option. Either the Arm one
   (e.g. **CAX11**) or the x86 one (e.g. **CX22**) works.
5. **Networking:** leave **Public IPv4** ticked (it's needed). IPv6 can stay
   ticked too.
6. **SSH keys:** skip this. Hetzner will email you a root password instead.
   Keep that email; you'll only need it for troubleshooting.
7. **Backups:** tick it (about 20% extra). This keeps 7 daily copies of the
   whole server.
8. **Cloud config:** this is the important step.
   * Open the file **`deploy/cloud-config.yaml`** (copy it from GitHub, or
     from the Dropbox project folder).
   * Change **`FAMILY_CODE=pancake42`** to your own secret family code: one
     word, no spaces, e.g. `FAMILY_CODE=greenfrog7`.
   * Leave `DOMAIN=play.silautron.com` as it is (unless you want a different
     address).
   * Paste **the whole file** into the *Cloud config* box.
9. **Name:** `wordspot`.
10. Click **Create & Buy now**.
11. After a few seconds the server appears with an **IPv4 address**, four
    numbers like `128.140.12.34`. **Copy it.** You need it in Part 3.

The server now sets itself up in the background, which takes about 5 minutes.

## Part 3: Point play.silautron.com at the server (5 minutes)

Your domain is managed at HostGator.

1. Log in to **HostGator**, then open **cPanel**.
2. Under **Domains**, click **Zone Editor**.
3. Next to **silautron.com**, click **+ A Record**. (If you only see
   **Manage**, click it, then **+ Add Record** and choose type **A**.)
4. Fill in:
   * **Name:** `play` (cPanel may show it as `play.silautron.com.`; that's fine)
   * **Address / Record:** the IPv4 address you copied
   * **TTL:** `300`, or leave the default
5. Click **Add Record** / **Save**.

**Don't change or delete any other records**, so your website keeps working.

## Part 4: Check it works

1. Wait about **10 minutes**. DNS changes can take up to an hour.
2. Open **https://play.silautron.com** in a browser. You should see Word Spot,
   with a padlock in the address bar.
3. Type a name, then the family code (asked once), and tap **Play on my own**
   to check a game starts.
4. **On each iPad:** open the address in **Safari**, tap **Share**, then
   **Add to Home Screen**. It now opens like an app.

That's it. 🎉

---

## If something isn't working

**The page doesn't load after an hour**

* Check the address points at your server: go to
  **https://www.whatsmydns.net**, type `play.silautron.com`, choose **A**, and
  check the result is your server's IPv4 address. If not, recheck Part 3.
* Check the server finished setting up. In the Hetzner Cloud Console, open the
  server and click the **Console** button (`>_`, top right). Log in as `root`
  with the password from Hetzner's email, then type:

  ```
  wordspot-status
  ```

  Both `wordspot` and `caddy` should say **Up**. To see the setup log:

  ```
  tail -n 30 /var/log/wordspot-install.log
  ```

**Changing the family code**

In the Hetzner Console (as above):

```
nano /opt/wordspot/.env
```

Change the `WORDSPOT_ACCESS_CODE=` line, press **Ctrl+O**, **Enter**,
**Ctrl+X**, then:

```
wordspot-update --force
```

Each iPad then asks for the new code the next time a game is started.

**Updating Word Spot straight away** (instead of waiting for the night):

```
wordspot-update
```

---

## Later

* **HostGator:** silautron.com renews on **17 April 2027**. Before then,
  decide whether to move the Laravel site onto this server (it can host it)
  and move the domain to a cheaper registrar (Cloudflare or Porkbun), then
  cancel HostGator. Move the domain **before** cancelling.
* **Email:** the domain still points its email at ProtonMail. You don't use
  it, so those records can be deleted when the domain moves; until then they
  do no harm.
* The same server can run other always-on projects later.

## How it works (for reference)

* `deploy/cloud-config.yaml` runs once when the server is created. It
  downloads and runs `deploy/install.sh`.
* `install.sh` installs Docker, the firewall (only ports 22, 80 and 443) and
  automatic security updates. It downloads Word Spot from GitHub (branch
  `word-spot-app`) into `/opt/wordspot/app` and starts two containers from
  `deploy/compose.yaml`:
  * **wordspot**: the game server
  * **caddy**: the web server in front, which gets and renews the free HTTPS
    certificate automatically
* Settings live in `/opt/wordspot/.env`. Nightly updates run
  `deploy/update.sh` from `/etc/cron.d/wordspot-update`.
* Password logins over SSH are switched off. The Hetzner web console still
  works with the root password.
