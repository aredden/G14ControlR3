Disable-PnpDevice -InstanceId (Get-PnpDevice -FriendlyName *"NVIDIA Geforce"* -Status OK).InstanceId -Confirm:$false

Enable-PnpDevice -InstanceId (Get-PnpDevice -FriendlyName *"NVIDIA Geforce"* ).InstanceId -Confirm:$false