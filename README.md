# FoodRescueNovaScotia
A Django website for Food Rescue NS that raises awareness about hunger insecurity in Nova Scotia through events, donations, community outreach, and local action.

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
