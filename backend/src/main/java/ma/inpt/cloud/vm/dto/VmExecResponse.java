package ma.inpt.cloud.vm.dto;

public record VmExecResponse(
    String status,
    String vmId,
    String command,
    String stdout,
    String stderr,
    int exitCode,
    String executedAt
) {}
