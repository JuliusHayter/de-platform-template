variable "project_id" {
  description = "The Google Cloud project everything lands in."
  type        = string
  # No default on purpose: a default project id silently builds in the wrong
  # place when somebody forgets to set it.
}

variable "group" {
  description = "Our group's short name, used in resource names."
  type        = string
}

variable "region" {
  description = "Location of every resource. Changing it on an existing bucket or dataset forces replacement."
  type        = string
  default     = "europe-west1"
}
