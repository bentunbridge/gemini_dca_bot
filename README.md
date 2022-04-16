# Gemini DCA Bot
A Dollar Cost Averaging Bot for [Gemini Exchange](https://www.gemini.com/uk).

Gemini is a cryptocurrency exchange which offers [10 complimentary withdrawals](https://support.gemini.com/hc/en-us/articles/209113906-What-are-the-transfer-limits-#:~:text=Customers%20are%20given%2010%20complimentary,withdrawal%20and%20charged%20a%20fee) which was largely why it was picked as the exchange for this bot.

The bot is containerised, the container image is created using the `Dockerfile` in the repo. The frequency of trades is controlled using the cron command-line utility. 

## Running the DCA Bot

To run the user will need to enter their credentials and inputs into the following configs.
We include an example config for each with the additional suffix `.example` e.g. `gemini_credentials.conf` &#8594; `gemini_credentials.conf.example`.

The configs are located in the `volume/` directory. This directory will be mounted to the container image and so files in the directory will be accessible from the containerised image. 

### Credential config:
**File Path:** `volume/configs/gemini_credentials.conf`  
It is possible to run the DCA bot in both a sandbox mode and a production mode.
The user will need to create and add the Gemini API credentials to the config file. To create sandbox and production level credentials, see the [How do I create an API key page](https://support.gemini.com/hc/en-us/articles/360031080191-How-do-I-create-an-API-key-).

The sandbox runmode will not make true buy orders, production mode will however. It is usually a good idea to try the bot out in the sandbox mode first before running in production to ensure the setup is as intended.
To learn more about the sandbox runmode, see the [Gemini sandbox site](https://exchange.sandbox.gemini.com/).

### Settings config:
**File Path:** `volume/configs/settings_btc_gemini.conf`
This config file contains the settings for the DCA bot. Here we can define the amount, currencies and stage granularities.

Here we can also add email credentials which is useful for setting up email monitoring alerts. 
It is advised that when using the email monitoring feature that a new single use email is created for this purpose rather than using an already used email account. Gmail credentials can be created on the [Gmail for developers](https://developers.google.com/gmail/api/auth/about-auth) page. Other email providers can also be used. The credentials should be added to the `SOURCE` and `PASS` inputs. The `DESTINATION` entry can be an email used for other purposes if preferred. 

The plot below shows an example of a plot included in the email monitoring message sent after a full cycle of the DCA bot. The blue line shows the limit orders that have been setup by the bot. The red and green candles show the price history of the trading pair. The star indicates where a limit order is triggered and completed.  
![15 Minute Interval Plot](https://user-images.githubusercontent.com/6554700/163692200-574d4ce4-cafc-41ec-9669-397a1c1123d8.png)

### Time triggered Bot
**File Path:** `cron/crontab`
We use the cron command-line utility to trigger the bot and timed intervals. This file can be altered to a preferred bot cadence. 
For example the cron command `0 */6 * * * root /bin/bash /code/run_gemini_dca_eth.sh` will run the `run_gemini_dca_eth.sh` bash script every 6 hours.

### Docker commands
We have included a series of bash scripts to run useful docker commands. Docker will need to be installed locally to run any of these commands. For more information on Docker, please see the [Docker site](https://www.docker.com/).
1) **Setup**: If setting up the bot for the first time, please run the `docker_commands/setup_docker.sh` script. This will build and register the container image. 
2) **Run**: To start the container run the `docker_commands/run_docker.sh` script. This will run the docker image until explicitly stopped. This has been setup with the `--restart unless-stopped` option which means that if the system is restarted, the docker will automatically be restarted as well without the need to rerun the `docker_commands/run_docker.sh` script again.
3) **View/Debug**: To interact with the running docker container, run the `docker_commands/view_container.sh` script. This is a useful way to debug the containerised image. This command will first list the active container images and ask for relevant docker id before launching an interactive session.
4) **Restart**: If any changes to the code or settings are made, e.g. cron settings, these will not take effect until the container image is restarted. This can be done by running the `docker_commands/restart_container.sh` script. Similarly to the view script, the command line action will list all active container images and prompt for the relevant one to restart. Once restarted the container image will continuously run until explicitly stopped using docker commands e.g. `docker stop $docker_id`.
