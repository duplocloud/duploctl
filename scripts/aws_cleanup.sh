
buckets=($(aws s3api list-buckets --query "Buckets[?contains(Name, 'duploctl')].Name" --output text))

# for each buck in the list print the name
for bucket in "${buckets[@]}"
do
  echo "Deleting bucket: $bucket"
  aws s3 rb s3://$bucket --force
done

# get a list of cloudformation stacks
stacks=($(aws cloudformation list-stacks --query "StackSummaries[?contains(StackName, 'duploctl')].StackName" --output text))

# for each stack in the list print the name
for stack in "${stacks[@]}"
do
  echo "Deleting stack: $stack"
  aws cloudformation delete-stack --stack-name $stack
done
