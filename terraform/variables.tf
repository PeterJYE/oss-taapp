variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "app_name" {
  description = "Name of the application"
  type        = string
  default     = "oss-taapp"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t2.micro" # Free tier eligible
}

variable "repo_url" {
  description = "Git repository URL to clone (required)"
  type        = string
  validation {
    condition     = var.repo_url != "" && can(regex("^https?://", var.repo_url))
    error_message = "repo_url must be a non-empty HTTP/HTTPS URL."
  }
}

variable "repo_branch" {
  description = "Git branch to checkout"
  type        = string
  default     = "main"
  validation {
    condition     = var.repo_branch != ""
    error_message = "repo_branch must be a non-empty string."
  }
}

variable "ssh_allowed_cidrs" {
  description = "CIDR blocks allowed to SSH (restrict to your IP for security)"
  type        = list(string)
  default     = ["0.0.0.0/0"] # WARNING: Allows SSH from anywhere - restrict in production!
}

