config_file="/var/volume/configs/settings_btc_gemini.conf"
run_mode="production"

last_run_log="/var/log/last_run_btc.out"

echo "BTC - `date`" > $last_run_log
/usr/local/bin/python3 /code/run_gemini_dca.py $config_file $run_mode &>> $last_run_log
echo "Finish - `date`" >> $last_run_log
