package ma.inpt.cloud.vm.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.util.List;

/**
 * Payload sent by the client when provisioning a new Virtual Machine.
 */
public record CreateVmRequest(
    @NotBlank(message = "VM name is required")
    @Size(min = 3, max = 50, message = "VM name must be between 3 and 50 characters")
    String name,

    @NotBlank(message = "Operating system must be specified")
    String os,

    @Min(value = 1, message = "Minimum 1 vCPU required")
    @Max(value = 4, message = "Maximum 4 vCPU allowed per VM")
    int cpu,

    @Min(value = 512, message = "Minimum 512 MB RAM required")
    @Max(value = 4096, message = "Maximum 4096 MB RAM allowed")
    int ramMb,

    @Min(value = 10, message = "Minimum 10 GB disk required")
    @Max(value = 100, message = "Maximum 100 GB disk allowed")
    int diskGb,

    String sshPublicKey,

    String initialPassword,

    List<Integer> openPorts
) {}
