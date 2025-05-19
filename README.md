# High level code


#### Supervisor Configuration

Create a configuration file for the script in `/etc/supervisor/supervisord.conf`

```ini
sudo nano /etc/supervisor/supervisord.conf

add program

[program:telegram_blood_pressure]
command=/home/gws/project/llm_in_action/BloodPressure/run_blood_pressure.sh
directory=directory=/home/gws/project/llm_in_action/BloodPressure
autostart=true
autorestart=true
stderr_logfile=/home/gws/project/llm_in_action/BloodPressure/log/run_cost_tracker.err.log
stdout_logfile=/home/gws/project/llm_in_action/BloodPressure/log/run_cost_tracker.out.log
stopasgroup=true
killasgroup=true
```

#### Update Supervisor

Once the configuration is added, update `supervisord` to read the new configuration:

```bash
sudo supervisorctl reread
sudo supervisorctl update
```

#### Start the Program

To start the program, use:

```bash
sudo supervisorctl start telegram_cost_tracker
```
