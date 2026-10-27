package ma.inpt.cloud.vm.dto;

import com.fasterxml.jackson.annotation.JsonAlias;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public record VmExecResponse(
    String status,
    @JsonProperty("vmId") @JsonAlias("vm_id") String vmId,
    String command,
    String stdout,
    String stderr,
    @JsonProperty("exitCode") @JsonAlias("exit_code") int exitCode,
    @JsonProperty("executedAt") @JsonAlias("executed_at") String executedAt
) {}
