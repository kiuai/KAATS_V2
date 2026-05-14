// ─────────────────────────────────────────────────────────────────────────────
// KAATS — Azure Monitor Alert Rules
// Fires on critical SLO breaches and infrastructure anomalies.
// All alerts target the Log Analytics workspace via KQL queries.
// ─────────────────────────────────────────────────────────────────────────────

@description('Azure region')
param location string

@description('Resource suffix (appName-env)')
param suffix string

@description('Log Analytics Workspace resource ID')
param logAnalyticsWorkspaceId string

@description('Application Insights resource ID')
param appInsightsId string

@description('Email address(es) for alert notifications (comma-separated)')
param alertEmailAddress string = ''

@description('Slack webhook URL for critical alerts (optional)')
param slackWebhookUrl string = ''

// ─────────────────────────────────────────────────────────────────────────────
// Action Group — where alerts are sent
// ─────────────────────────────────────────────────────────────────────────────

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: 'ag-kaats-${suffix}'
  location: 'global'
  tags: { component: 'monitoring' }
  properties: {
    groupShortName: 'KAATS'
    enabled: true
    emailReceivers: alertEmailAddress != '' ? [
      {
        name: 'ops-email'
        emailAddress: alertEmailAddress
        useCommonAlertSchema: true
      }
    ] : []
    webhookReceivers: slackWebhookUrl != '' ? [
      {
        name: 'slack'
        serviceUri: slackWebhookUrl
        useCommonAlertSchema: true
      }
    ] : []
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Alert: High 5xx Error Rate  (>1 % of requests in last 5 min)
// ─────────────────────────────────────────────────────────────────────────────

resource alert5xxRate 'Microsoft.Insights/scheduledQueryRules@2022-06-15' = {
  name: 'alert-5xx-rate-${suffix}'
  location: location
  tags: { component: 'monitoring', severity: 'critical' }
  properties: {
    description: 'More than 1% of HTTP requests returned 5xx in the last 5 minutes'
    severity: 1   // 0=Critical, 1=Error, 2=Warning, 3=Informational
    enabled: true
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    scopes: [logAnalyticsWorkspaceId]
    criteria: {
      allOf: [
        {
          query: '''
            AppRequests
            | where TimeGenerated > ago(5m)
            | summarize
                total     = count(),
                errors    = countif(ResultCode >= 500)
              by bin(TimeGenerated, 5m)
            | where total > 10
            | extend error_rate = toreal(errors) / toreal(total) * 100
            | where error_rate > 1
          '''
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [actionGroup.id]
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Alert: High P99 Request Latency  (>3 000 ms in last 5 min)
// ─────────────────────────────────────────────────────────────────────────────

resource alertHighLatency 'Microsoft.Insights/scheduledQueryRules@2022-06-15' = {
  name: 'alert-latency-p99-${suffix}'
  location: location
  tags: { component: 'monitoring', severity: 'warning' }
  properties: {
    description: 'P99 request latency exceeded 3 000 ms in the last 5 minutes'
    severity: 2
    enabled: true
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    scopes: [logAnalyticsWorkspaceId]
    criteria: {
      allOf: [
        {
          query: '''
            AppRequests
            | where TimeGenerated > ago(5m)
            | summarize p99_ms = percentile(DurationMs, 99) by bin(TimeGenerated, 5m)
            | where p99_ms > 3000
          '''
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [actionGroup.id]
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Alert: Agent Execution Failures  (>10 % in last 15 min)
// ─────────────────────────────────────────────────────────────────────────────

resource alertAgentFailures 'Microsoft.Insights/scheduledQueryRules@2022-06-15' = {
  name: 'alert-agent-failures-${suffix}'
  location: location
  tags: { component: 'monitoring', severity: 'critical' }
  properties: {
    description: 'More than 10% of agent executions failed in the last 15 minutes'
    severity: 1
    enabled: true
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    scopes: [logAnalyticsWorkspaceId]
    criteria: {
      allOf: [
        {
          query: '''
            AppTraces
            | where TimeGenerated > ago(15m)
            | where Message has "agent.execute"
            | extend outcome = iff(Message has "failed" or Message has "timeout", "failed", "ok")
            | summarize
                total  = count(),
                failed = countif(outcome == "failed")
              by bin(TimeGenerated, 15m)
            | where total >= 5
            | extend failure_rate = toreal(failed) / toreal(total) * 100
            | where failure_rate > 10
          '''
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [actionGroup.id]
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Alert: Database Readiness Check Failures  (any failure in 5 min)
// ─────────────────────────────────────────────────────────────────────────────

resource alertDbReadiness 'Microsoft.Insights/scheduledQueryRules@2022-06-15' = {
  name: 'alert-db-readiness-${suffix}'
  location: location
  tags: { component: 'monitoring', severity: 'critical' }
  properties: {
    description: 'Database readiness check failed — /health/ready returning degraded'
    severity: 1
    enabled: true
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    scopes: [logAnalyticsWorkspaceId]
    criteria: {
      allOf: [
        {
          query: '''
            AppTraces
            | where TimeGenerated > ago(5m)
            | where Message has "health.readiness"
            | extend db_status = extract('"check_database":"([^"]+)"', 1, Message)
            | where db_status == "degraded"
            | summarize failures = count() by bin(TimeGenerated, 5m)
            | where failures >= 3
          '''
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [actionGroup.id]
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Alert: Unhandled Exceptions Spike  (>5 in 5 min)
// ─────────────────────────────────────────────────────────────────────────────

resource alertExceptionSpike 'Microsoft.Insights/scheduledQueryRules@2022-06-15' = {
  name: 'alert-exceptions-${suffix}'
  location: location
  tags: { component: 'monitoring', severity: 'error' }
  properties: {
    description: 'More than 5 unhandled exceptions in 5 minutes'
    severity: 1
    enabled: true
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    scopes: [logAnalyticsWorkspaceId]
    criteria: {
      allOf: [
        {
          query: '''
            AppExceptions
            | where TimeGenerated > ago(5m)
            | summarize exceptions = count() by bin(TimeGenerated, 5m)
            | where exceptions > 5
          '''
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [actionGroup.id]
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Alert: Scheduler Did Not Fire  (no "scheduler.evaluation_complete" in 5 min)
// ─────────────────────────────────────────────────────────────────────────────

resource alertSchedulerSilent 'Microsoft.Insights/scheduledQueryRules@2022-06-15' = {
  name: 'alert-scheduler-silent-${suffix}'
  location: location
  tags: { component: 'monitoring', severity: 'warning' }
  properties: {
    description: 'Scheduler has not produced an evaluation log in the last 5 minutes'
    severity: 2
    enabled: true
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    scopes: [logAnalyticsWorkspaceId]
    criteria: {
      allOf: [
        {
          query: '''
            AppTraces
            | where TimeGenerated > ago(5m)
            | where Message has "scheduler.evaluation_complete"
            | summarize count() by bin(TimeGenerated, 5m)
            | where count_ == 0 or isnull(count_)
          '''
          timeAggregation: 'Count'
          operator: 'LessThan'
          threshold: 1
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [actionGroup.id]
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────

output actionGroupId string = actionGroup.id
