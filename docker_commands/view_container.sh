docker ps

read -p "   Enter docker id >>> " docker_id
if [ "$docker_id" == "" ]
then
  docker_id=""
fi

docker exec -it $docker_id bash