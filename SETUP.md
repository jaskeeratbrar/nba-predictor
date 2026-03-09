# NBA Predictor — Setup Cheatsheet

## Prerequisites
```bash
python3 --version   # need 3.8+
curl --version      # pre-installed on macOS/Linux
git --version
```

## GitHub SSH
```bash
ssh -T git@github.com                        # test — should say "Hi jaskeeratbrar!"

# If it fails:
ssh-keygen -t ed25519 -C "your@email.com"   # hit Enter through all prompts
cat ~/.ssh/id_ed25519.pub                    # copy output → GitHub → Settings → SSH Keys
ssh -T git@github.com                        # test again
```

## Clone + Setup
```bash
git clone git@github.com:jaskeeratbrar/nba-predictor.git
cd nba-predictor
bash setup.sh       # initializes DB, starts server, installs cron jobs
```

## Verify
```bash
curl http://localhost:6789/status            # should return {"status": "ok"}
curl "http://localhost:6789/run?fmt=text"    # today's picks
```

## Timezone
```bash
date    # check what timezone your machine is in
crontab -e   # adjust times after setup.sh runs
```

Cron times by timezone — all target 6 PM ET for predictions:

| Job | ET | MT (−2h) | PT (−3h) | UTC (+5h) |
|-----|-----|----------|----------|-----------|
| Predictions | 18:00 | 16:00 | 15:00 | 23:00 |
| Post-game analysis | 09:00 | 07:00 | 06:00 | 14:00 |
| DB backup | 10:00 | 08:00 | 09:00 | 15:00 |

After `bash setup.sh`, run `crontab -e` and update the hours to match your timezone.

## Vercel (one-time)
1. vercel.com → Add New Project → import `nba-predictor`
2. Output Directory: `public` — leave build command blank
3. Deploy → done. Cron auto-pushes every 6 PM, Vercel auto-redeploys.

---

## Cron Schedule
| Time (ET) | Job |
|-----------|-----|
| 6:00 PM | Predictions → dashboard → git push → Vercel redeploys |
| 9:00 AM | Post-game analysis + update learning ledger |
| 10:00 AM | DB backup |

## Run Timing
| Time (ET) | Event |
|-----------|-------|
| 5:00 PM | NBA injury report deadline |
| 5:30 PM | ESPN API updates |
| **6:00 PM** | **Best time to run** |
| 7:00 PM | First tip-off |

---

## Manual Commands
```bash
python3 run_predictions.py                   # today's picks
python3 run_predictions.py 2026-03-15        # specific date
python3 run_predictions.py --analyze 2026-03-07   # post-game analysis
python3 migrate.py                           # import history into DB (run once)
```

## Server Endpoints
```
GET /status
GET /run
GET /run?date=YYYY-MM-DD
GET /run?fmt=text
GET /analyze?date=YYYY-MM-DD
```

---

## Troubleshooting
| Problem | Fix |
|---------|-----|
| Server not running | `python3 server.py &` |
| macOS service down | `launchctl unload/load ~/Library/LaunchAgents/com.nbapredictor.server.plist` |
| Linux service down | `sudo systemctl restart nba-predictor` |
| Cron not pushing | `ssh -T git@github.com` — SSH key probably missing |
| No games found | ESPN downtime — retry in 10 min |
| Vercel not updating | Check `cron.log` and confirm commit appeared on GitHub |

## Logs
```bash
tail -f server.log
tail -f cron.log
sudo journalctl -u nba-predictor -f   # Linux only
```
