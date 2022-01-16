relative_path="`dirname \"$0\"`"
echo "Relative Path: $relative_path"
docker ps

read -p "   Enter docker id >>> " docker_id
if [ "$docker_id" == "" ]
then
  docker_id=""
fi

echo "Stopping Docker ID: $docker_id"
docker stop $docker_id
docker rm $docker_id
echo "Running setup_docker.sh"
bash $relative_path/setup_docker.sh
echo "Running run_docker.sh"
bash $relative_path/run_docker.sh