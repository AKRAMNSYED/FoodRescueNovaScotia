# FoodRescueNovaScotia
A Django website for Food Rescue NS that raises awareness about hunger insecurity in Nova Scotia through events, donations, community outreach, and local action.

## Keep accounts across Railway redeploys

The site uses SQLite, which lives inside the container and is erased on every deploy unless a volume is attached. In Railway:

1. Open the service, then **Settings > Volumes** (or right-click the canvas > **Volume**) and add a volume mounted at `/data`.
2. Redeploy. The app detects `RAILWAY_VOLUME_MOUNT_PATH` automatically and stores `db.sqlite3` and uploaded `media/` on the volume.
3. Create your admin accounts again (below). They will now survive future deploys.

Accounts created before the volume was attached are not copied over.

## Create the main admin account on Railway

After deploying, open the Railway service shell and run:

```text
python manage.py create_main_admin
```

The command prompts for a username and a password twice; password input is hidden. It creates a Django superuser with full admin access and refuses to change an existing account.

## Create a subadmin account on Railway

In the Railway service shell, run:

```text
python manage.py create_subadmin
```

The command prompts for a username and a password twice; password input is hidden. It creates an active staff-only account that is not a superuser and refuses to change an existing account.
