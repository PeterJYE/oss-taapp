terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Use Ubuntu 22.04 AMI (has Python 3.11 available)
# Ubuntu 22.04 LTS AMI for us-east-1 (updated Dec 2024)
locals {
  ubuntu_ami = "ami-0030e4319cbf4dbf2" # Ubuntu 22.04 LTS for us-east-1
}

# Security Group - Allow HTTP for services and SSH for management
resource "aws_security_group" "app_sg" {
  name        = "${var.app_name}-sg"
  description = "Security group for ${var.app_name} services"

  # Allow HTTP for AI service (port 8000)
  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "AI Service"
  }

  # Allow HTTP for Ticket service (port 8001)
  ingress {
    from_port   = 8001
    to_port     = 8001
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Ticket Service"
  }

  # Allow SSH for management (optional - restrict to your IP)
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ssh_allowed_cidrs
    description = "SSH"
  }

  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.app_name}-sg"
  }
}

# EC2 Instance
resource "aws_instance" "app_server" {
  ami           = local.ubuntu_ami
  instance_type = var.instance_type

  vpc_security_group_ids = [aws_security_group.app_sg.id]

  # SSH key for access
  key_name = "oss-taapp-key-v2"

  # IAM role for accessing Parameter Store (optional)
  iam_instance_profile = aws_iam_instance_profile.app_profile.name

  # User data script to deploy and start services
  user_data = base64encode(templatefile("${path.module}/user-data.sh", {
    repo_url        = var.repo_url
    repo_branch      = var.repo_branch
    ai_service_port  = 8000
    ticket_port      = 8001
  }))

  tags = {
    Name = var.app_name
  }
}

# IAM Role for EC2 instance (to access Parameter Store for env vars)
resource "aws_iam_role" "app_role" {
  name = "${var.app_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

# CloudWatch Log Group will be created automatically by the agent
# (if IAM permissions allow, otherwise create manually in AWS Console)

# IAM Policy to read Parameter Store and write CloudWatch Logs
resource "aws_iam_role_policy" "app_policy" {
  name = "${var.app_name}-policy"
  role = aws_iam_role.app_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ]
        Resource = "arn:aws:ssm:${var.aws_region}:*:parameter/${var.app_name}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = [
          "arn:aws:logs:${var.aws_region}:*:log-group:/aws/ec2/${var.app_name}",
          "arn:aws:logs:${var.aws_region}:*:log-group:/aws/ec2/${var.app_name}:*"
        ]
      }
    ]
  })
}

# IAM Instance Profile
resource "aws_iam_instance_profile" "app_profile" {
  name = "${var.app_name}-profile"
  role = aws_iam_role.app_role.name
}

