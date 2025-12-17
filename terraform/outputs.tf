output "public_ip" {
  description = "Public IP address of the EC2 instance"
  value       = aws_instance.app_server.public_ip
}

output "ai_service_url" {
  description = "URL to access AI service"
  value       = "http://${aws_instance.app_server.public_ip}:8000"
}

output "ticket_service_url" {
  description = "URL to access Ticket service"
  value       = "http://${aws_instance.app_server.public_ip}:8001"
}

output "metrics_url" {
  description = "URL to access telemetry metrics"
  value       = "http://${aws_instance.app_server.public_ip}:8000/metrics"
}

output "health_check_url" {
  description = "URL to check AI service health"
  value       = "http://${aws_instance.app_server.public_ip}:8000/health"
}

output "ssh_command" {
  description = "SSH command to connect to the server"
  value       = "ssh -i <your-key.pem> ubuntu@${aws_instance.app_server.public_ip}"
}

output "cloudwatch_logs_url" {
  description = "CloudWatch Logs URL"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#logsV2:log-groups/log-group/$252Faws$252Fec2$252F${var.app_name}"
}

