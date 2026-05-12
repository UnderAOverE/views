Top 4 Investigative Metrics for AVI Dashboard
Based on your AVI support guy's advice (focus on SE and VM, not VS), here are the 4 metrics I'd recommend for your production support team. I picked these because they cover the four classic failure domains — CPU, Memory, Network drops, and Packet headroom — and each one has a clear "this is bad" threshold that doesn't require deep AVI knowledge to interpret.
1. SE CPU Usage (from AviServiceEngine)
Metric: CPUUsage
Why: This is the single most predictive metric for SE health. When SE CPU saturates, packet processing latency spikes, connections queue up, and everything downstream looks broken. AVI's own packet-processing threads (dispatcher + proxy) are CPU-bound, so this is the first thing to watch.
Thresholds to alert on:

Warning: > 70% sustained for 5 min
Critical: > 85% sustained for 5 min

A useful refinement: cross-check against the VM's cpu_demandPct from VirtualMachineMetrics — if SE CPU is fine but VM cpu_demandPct is high, you have a noisy neighbor or host contention problem rather than an AVI problem.
2. SE RX Packet Drop Rate (derived from AviServiceEngine)
Metric: RXPacketsDrop / RXPackets * 100 (drop percentage)
Why: Raw RXPacketsDrop is misleading because a busy SE will always drop some packets. What matters is the drop ratio. In your sample, SE 10.226.69.6 shows 237 drops out of 32,933 packets ≈ 0.72% drop rate, which is already worth investigating (anything > 0.1% sustained usually indicates an SE under stress or an undersized flow table).
Thresholds:

Warning: > 0.1% sustained
Critical: > 1% sustained

This is way more actionable than raw counters and won't false-alarm on healthy busy SEs.
3. VM Memory Consumed % (from VirtualMachineMetrics)
Metric: mem_consumedPct
Why: Your sample shows ecs_cluster1-se-8 at 99.97% — that is screaming. SEs that run out of memory will start dropping connections, failing health checks, or get OOM-killed by the hypervisor. Memory pressure on SE VMs is one of the most common silent killers because the AVI SE process itself reports a healthy MemoryUsage: 18 while the underlying VM is suffocating.
Thresholds:

Warning: > 90%
Critical: > 95%

Also worth pairing with mem_swapped_average — anything above 0 on a swap counter for an SE VM is a red flag.
4. VM Network Peak Utilization (from VirtualMachineMetrics)
Metric: net_20_sec_peak_packetsPerSec (or net_20_sec_peak_usage_average for bandwidth)
Why: This tells you if you're approaching the pNIC / vNIC ceiling on the underlying VM. SEs that hit the network ceiling will show as "slow VS" but the root cause is the VM hitting line rate. The 20-second peak is more useful than the average because microbursts cause real production pain that 5-minute averages hide.
Thresholds (depends on your vNIC speed — assuming 10 Gbps):

Warning: > 60% of line rate sustained
Critical: > 80% of line rate sustained, or any sample > 95%

Cross-reference with net_droppedTxPct_max — if both are climbing together, you're capacity-constrained and need to scale out SEs.

Quick summary table for the dashboard
#MetricSourceWarn / CritWhat it tells you1CPU UsageSE70% / 85%SE packet-processing saturation2RX Drop % (derived)SE0.1% / 1%SE is overwhelmed or misconfigured3Memory Consumed %VM90% / 95%SE VM about to OOM4Net Peak pps / BwVM60% / 80% of line rateHitting NIC ceiling
On the Virtual Service metrics
Your AVI guy is right — keep OpenConnections, ConnectionsPerSecond, AverageBandwidth, etc. visible on the dashboard as context panels (so support can see "yes, traffic is high right now") but don't put alerts on them. When a VS metric looks bad, the first action should always be: check the 4 metrics above on the SEs serving that VS. That's the investigative flow you want to train the team into.
One small note for the dashboard design: group the panels as "What's happening" (VS metrics, no alerts) on top and "Why it's happening" (the 4 SE/VM metrics, with alerts) below. That visually reinforces the investigation order.You said: ok thanks, he also mentioned to include the network tx dropped and rx dropped summation metric too for vmok thanks, he also mentioned to include the network tx dropped and rx dropped summation metric too for vm5:53 PMClaude responded: Updated: Top 5 Investigative Metrics for AVI DashboardUpdated: Top 5 Investigative Metrics for AVI Dashboard
Good call adding those — your AVI guy is right that VM-level drops catch a different class of problem than SE-level drops. SE drops tell you the AVI process is overwhelmed; VM drops tell you the hypervisor/vNIC layer is dropping packets before AVI ever sees them. Different root causes, different fixes.
1. SE CPU Usage (from AviServiceEngine)
Metric: CPUUsage
Why: Single most predictive metric for SE health. Packet processing threads are CPU-bound, so saturation here cascades into everything else.
Thresholds: Warn > 70%, Crit > 85% (sustained 5 min)
Cross-check with VM cpu_demandPct — if SE CPU is fine but VM demand is high, suspect host contention/noisy neighbor.
2. SE RX Packet Drop Rate (derived from AviServiceEngine)
Metric: RXPacketsDrop / RXPackets * 100
Why: Raw drops are misleading on busy SEs; the ratio is what matters. Your sample SE 10.226.69.6 is at ~0.72% — already worth a look.
Thresholds: Warn > 0.1%, Crit > 1% (sustained)
3. VM Memory Consumed % (from VirtualMachineMetrics)
Metric: mem_consumedPct
Why: Your ecs_cluster1-se-8 is at 99.97% — that's a ticking bomb. SE process reports healthy MemoryUsage: 18 while the VM is suffocating, which is exactly the kind of silent failure this catches.
Thresholds: Warn > 90%, Crit > 95%
Pair with mem_swapped_average — anything > 0 is a red flag.
4. VM Network Drops — RX & TX (from VirtualMachineMetrics) ⭐ new
Metrics: net_droppedRx_summation + net_droppedTx_summation (and the derived net_droppedTxPct_max)
Why: This catches problems below AVI — vNIC ring buffer overflows, hypervisor scheduling issues, pNIC contention, or DVS/portgroup misconfigurations. When these climb, AVI looks broken but it isn't; the packets never made it to the SE process.
How to read them:

RX drops → packets dropped on the way into the VM. Usually means the vNIC ring buffer is overflowing because the VM can't drain it fast enough (often CPU-related) or the host is overloaded.
TX drops → packets dropped on the way out. Often points to an upstream issue: vSwitch congestion, pNIC saturation, or QoS policies kicking in.
net_droppedTxPct_max → the normalized version, easier to alert on. Your sample shows 0.0013% which is fine; anything sustained above 0.01% is worth investigating.

Thresholds:

Warn: any non-zero RX drop sustained across 2+ intervals, OR net_droppedTxPct_max > 0.01%
Crit: RX or TX drops climbing monotonically, OR net_droppedTxPct_max > 0.1%

The key insight your AVI guy is pointing at: if SE drops are low but VM drops are high, the problem is the virtualization layer, not AVI — and that means escalating to the VMware/infra team, not the AVI team. This metric literally tells your support team which team to page.
5. VM Network Peak Utilization (from VirtualMachineMetrics)
Metric: net_20_sec_peak_packetsPerSec (and net_20_sec_peak_usage_average for bandwidth)
Why: Tells you when you're approaching the vNIC ceiling. 20-second peak catches microbursts that 5-minute averages hide.
Thresholds (assumes 10 Gbps vNIC): Warn > 60% line rate, Crit > 80% sustained or any sample > 95%
When this AND the VM drops from #4 are both climbing, you're capacity-bound and need to scale out SEs.

Updated dashboard summary
#MetricSourceWarn / CritPoints the finger at1CPU UsageSE70% / 85%AVI process saturation2RX Drop % (derived)SE0.1% / 1%AVI overwhelmed3Memory Consumed %VM90% / 95%SE VM about to OOM4Net Dropped RX/TXVMany sustained / climbingHypervisor/vNIC layer (not AVI)5Net Peak pps / BwVM60% / 80% line rateCapacity ceiling
Triage flow this enables
The nice thing about this set is it gives your support team a clean decision tree:

VS looks bad + #1 or #2 firing → AVI SE problem, look at SE config/scaling
VS looks bad + #3 firing → SE VM memory problem, restart SE or grow VM
VS looks bad + #4 firing but #1/#2 quiet → Infrastructure problem, page VMware/network team
VS looks bad + #5 firing → Capacity problem, scale out SEs
VS looks bad + nothing on #1–#5 → Not an AVI issue, look upstream/downstream

That last row is the most valuable one — it's how the team learns to not page the AVI team for every VS hiccup.
