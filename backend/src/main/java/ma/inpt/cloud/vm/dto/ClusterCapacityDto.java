package ma.inpt.cloud.vm.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Consolidated computing and memory capacity across the entire Raspberry Pi node fleet (Master + Workers).
 */
public record ClusterCapacityDto(
    @JsonProperty("total_nodes") int totalNodes,
    @JsonProperty("online_nodes") int onlineNodes,
    @JsonProperty("worker_nodes") int workerNodes,
    @JsonProperty("total_cpu_cores") int totalCpuCores,
    @JsonProperty("total_ram_mb") int totalRamMb,
    @JsonProperty("used_ram_mb") int usedRamMb,
    @JsonProperty("free_ram_mb") int freeRamMb,
    @JsonProperty("ram_usage_pct") int ramUsagePct,
    @JsonProperty("total_disk_gb") double totalDiskGb,
    @JsonProperty("used_disk_gb") double usedDiskGb,
    @JsonProperty("free_disk_gb") double freeDiskGb,
    @JsonProperty("disk_usage_pct") int diskUsagePct,
    @JsonProperty("total_active_vms") int totalActiveVms
) {}
