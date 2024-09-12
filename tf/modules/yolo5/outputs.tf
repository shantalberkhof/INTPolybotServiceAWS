# Outputs the ID of the YOLOv5 launch template (ASG) and the EC2 instance type for YOLOv5 instance

output "launch_template_id" {
  value = aws_launch_template.tf-yolo5-lt.id
}

output "yolo5_instance_type" {
  value = data.aws_ec2_instance_types.yolo5_instance_types.instance_types[0]
}