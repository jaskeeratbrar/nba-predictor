#!/bin/bash
YESTERDAY=$(python3 -c "from datetime import date, timedelta; print((date.today()-timedelta(1)).strftime('%Y-%m-%d'))")
curl -s "http://localhost:6789/analyze?date=$YESTERDAY"
