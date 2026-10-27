package ma.inpt.cloud.vm.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record VmExecRequest(
    @NotBlank(message = "Command cannot be blank")
    @Size(max = 1000, message = "Command cannot exceed 1000 characters")
    String command
) {}
