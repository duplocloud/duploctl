
buckets=($(aws s3api list-buckets --query "Buckets[?contains(Name, 'duploctl')].Name" --output text))

# for each buck in the list print the name
for bucket in "${buckets[@]}"
do
  echo "Deleting bucket: $bucket"
  aws s3 rb s3://$bucket --force
done

