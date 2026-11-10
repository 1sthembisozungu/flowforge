
"use strict";

// ============================================================
// 1. DOM ELEMENTS
// ============================================================

const API_BASE = "/api";

// Dashboard statistics
const totalWorkflowsElement = document.getElementById("total-workflows");
const activeWorkflowsElement = document.getElementById("active-workflows");
const totalExecutionsElement = document.getElementById("total-executions");

// Workflow section
const workflowListElement = document.getElementById("workflow-list");
const workflowMessageElement = document.getElementById("workflow-message");
const refreshWorkflowsButton = document.getElementById("refresh-workflows");

// Workflow builder
const createWorkflowForm = document.getElementById("create-workflow-form");
const workflowNameInput = document.getElementById("workflow-name");
const workflowDescriptionInput = document.getElementById("workflow-description");
const workflowStatusInput = document.getElementById("workflow-status");

const triggerEventInput = document.getElementById("trigger-event");

const conditionFieldInput = document.getElementById("condition-field");
const conditionOperatorInput = document.getElementById("condition-operator");
const conditionValueInput = document.getElementById("condition-value");

const actionTypeInput = document.getElementById("action-type");
const actionMessageInput = document.getElementById("action-message");

const createWorkflowButton = document.getElementById("create-workflow-button");
const createWorkflowMessage = document.getElementById("create-workflow-message");

// Workflow testing
const executionForm = document.getElementById("execution-form");
const workflowSelectElement = document.getElementById("workflow-id");
const executionSubjectInput = document.getElementById("email-subject");
const executionBodyInput = document.getElementById("email-body");
const executeButton = document.getElementById("execute-button");

const executionResultElement = document.getElementById("execution-result");
const executionResultContent = document.getElementById("execution-result-content");

// Execution history
const historyMessageElement = document.getElementById("history-message");
const historyTableBody = document.getElementById("history-table-body");
const refreshHistoryButton = document.getElementById("refresh-history");


// ============================================================
// 2. HELPER FUNCTIONS
// ============================================================

async function getResponseData(response) {
    let data;

    try {
        data = await response.json();
    } catch {
        throw new Error("The server returned an invalid response.");
    }

    if (!response.ok) {
        throw new Error(
            data.error || data.message || `Request failed: ${response.status}`
        );
    }

    return data;
}


function createTextElement(tagName, text, className = "") {
    const element = document.createElement(tagName);

    element.textContent = text ?? "";

    if (className) {
        element.className = className;
    }

    return element;
}


function formatDate(dateValue) {
    if (!dateValue) {
        return "—";
    }

    const date = new Date(dateValue);

    if (Number.isNaN(date.getTime())) {
        return "—";
    }

    return date.toLocaleString();
}


function showMessage(element, message, isError = false) {
    if (!element) return;

    element.textContent = message;
    element.classList.toggle("error", isError);
    element.classList.toggle("success", !isError);
}


function setButtonLoading(button, isLoading, normalText, loadingText) {
    if (!button) return;

    button.disabled = isLoading;
    button.textContent = isLoading ? loadingText : normalText;
}


// ============================================================
// 3. LOAD WORKFLOWS
// ============================================================

async function loadWorkflows() {
    try {
        showMessage(workflowMessageElement, "Loading workflows...");

        const response = await fetch(`${API_BASE}/workflows`, {
            method: "GET",
            credentials: "same-origin"
        });

        const data = await getResponseData(response);
        const workflows = data.workflows || [];

        // Update workflow statistics.
        if (totalWorkflowsElement) {
            totalWorkflowsElement.textContent = workflows.length;
        }

        const activeWorkflows = workflows.filter(
            workflow => workflow.status === "active"
        );

        if (activeWorkflowsElement) {
            activeWorkflowsElement.textContent = activeWorkflows.length;
        }

        displayWorkflows(workflows);
        populateWorkflowSelect(workflows);

        showMessage(
            workflowMessageElement,
            workflows.length
                ? `${workflows.length} workflow(s) loaded successfully.`
                : "You have not created any workflows yet."
        );

        // Load the execution count across the available workflows.
        await loadTotalExecutionCount(workflows);

        // Load history for the currently selected workflow.
        if (workflowSelectElement?.value) {
            await loadExecutionHistory(workflowSelectElement.value);
        } else {
            clearExecutionHistory();
        }

    } catch (error) {
        console.error("Error loading workflows:", error);

        showMessage(
            workflowMessageElement,
            error.message,
            true
        );
    }
}


// ============================================================
// 4. DISPLAY WORKFLOW CARDS
// ============================================================

function displayWorkflows(workflows) {
    if (!workflowListElement) return;

    workflowListElement.replaceChildren();

    if (workflows.length === 0) {
        workflowListElement.appendChild(
            createTextElement(
                "p",
                "No workflows created yet.",
                "empty-message"
            )
        );

        return;
    }

    workflows.forEach(workflow => {
        const card = document.createElement("article");
        card.className = "workflow-card";

        const heading = createTextElement("h3", workflow.name);

        const description = createTextElement(
            "p",
            workflow.description || "No description provided."
        );

        const status = createTextElement(
            "span",
            workflow.status,
            `status status-${workflow.status}`
        );

        const createdAt = createTextElement(
            "small",
            `Created: ${formatDate(workflow.created_at)}`
        );

        const stepSummary = document.createElement("div");
        stepSummary.className = "workflow-step-summary";
        stepSummary.textContent = "Loading workflow steps...";

        const testButton = createTextElement(
            "button",
            "Test workflow",
            "button secondary test-workflow-button"
        );

        testButton.type = "button";
        testButton.dataset.workflowId = workflow.id;

        const historyButton = createTextElement(
            "button",
            "View history",
            "button secondary view-history-button"
        );

        historyButton.type = "button";
        historyButton.dataset.workflowId = workflow.id;

        card.append(
            heading,
            description,
            status,
            createdAt,
            stepSummary,
            testButton,
            historyButton
        );

        workflowListElement.appendChild(card);

        // Load the trigger, condition and action for this workflow.
        loadWorkflowSteps(workflow.id, stepSummary);
    });
}


// ============================================================
// 5. LOAD WORKFLOW STEPS
// ============================================================

async function loadWorkflowSteps(workflowId, container) {
    try {
        const response = await fetch(
            `${API_BASE}/workflows/${workflowId}/steps`,
            {
                method: "GET",
                credentials: "same-origin"
            }
        );

        const data = await getResponseData(response);

        displayWorkflowSteps(data.steps || [], container);

    } catch (error) {
        console.error(
            `Could not load steps for workflow ${workflowId}:`,
            error
        );

        container.textContent = "Unable to load workflow steps.";
    }
}


function displayWorkflowSteps(steps, container) {
    container.replaceChildren();

    if (steps.length === 0) {
        container.appendChild(
            createTextElement(
                "p",
                "No steps configured.",
                "empty-steps"
            )
        );

        return;
    }

    steps.forEach(step => {
        const item = document.createElement("div");
        item.className = "workflow-step-item";

        const configuration = step.configuration || {};

        let title;
        let description;

        switch (step.step_type) {
            case "trigger":
                title = "Trigger";
                description = `Event: ${configuration.event || "Not configured"}`;
                break;

            case "condition":
                title = "Condition";
                description =
                    `${configuration.field || "field"} ` +
                    `${configuration.operator || "operator"} ` +
                    `"${configuration.value || ""}"`;
                break;

            case "action":
                title = "Action";
                description =
                    configuration.message ||
                    configuration.type ||
                    "Not configured";
                break;

            default:
                title = step.step_type;
                description = "Unknown workflow step.";
        }

        item.append(
            createTextElement(
                "strong",
                `Step ${step.step_order}: ${title}`
            ),
            createTextElement("p", description)
        );

        container.appendChild(item);
    });
}


// ============================================================
// 6. POPULATE WORKFLOW DROPDOWN
// ============================================================

function populateWorkflowSelect(workflows) {
    if (!workflowSelectElement) return;

    const previousValue = workflowSelectElement.value;

    workflowSelectElement.replaceChildren();

    const defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = "Select a workflow";

    workflowSelectElement.appendChild(defaultOption);

    workflows.forEach(workflow => {
        const option = document.createElement("option");

        option.value = workflow.id;
        option.textContent = workflow.name;

        workflowSelectElement.appendChild(option);
    });

    // Preserve the user's previous selection when possible.
    const previousWorkflowExists = workflows.some(
        workflow => String(workflow.id) === previousValue
    );

    if (previousWorkflowExists) {
        workflowSelectElement.value = previousValue;
    } else if (workflows.length > 0) {
        workflowSelectElement.value = String(workflows[0].id);
    }
}


// ============================================================
// 7. CREATE WORKFLOW
// ============================================================


async function createWorkflow(event) {
    // Prevent the browser from submitting and refreshing the page.
    event.preventDefault();

    // 1. Collect values from the workflow builder form.
    const workflowName = workflowNameInput.value.trim();
    const workflowDescription = workflowDescriptionInput.value.trim();
    const workflowStatus = workflowStatusInput.value;

    const triggerEvent = triggerEventInput.value;

    const conditionField = conditionFieldInput.value;
    const conditionOperator = conditionOperatorInput.value;
    const conditionValue = conditionValueInput.value.trim();

    const actionType = actionTypeInput.value;
    const actionMessage = actionMessageInput.value.trim();

    // 2. Validate the required fields.
    if (
        !workflowName ||
        !conditionValue ||
        !actionMessage
    ) {
        showMessage(
            createWorkflowMessage,
            "Please complete all required fields.",
            true
        );

        return;
    }

    // 3. Prepare all three workflow steps in JavaScript.
    const steps = [
        {
            step_type: "trigger",
            step_order: 1,
            configuration: {
                event: triggerEvent
            }
        },
        {
            step_type: "condition",
            step_order: 2,
            configuration: {
                field: conditionField,
                operator: conditionOperator,
                value: conditionValue
            }
        },
        {
            step_type: "action",
            step_order: 3,
            configuration: {
                type: actionType,
                message: actionMessage
            }
        }
    ];

    // 4. Show that workflow creation is in progress.
    setButtonLoading(
        createWorkflowButton,
        true,
        "Create workflow",
        "Creating workflow..."
    );

    try {
        // 5. Send the workflow and all three steps in ONE request.
        const response = await fetch(
            `${API_BASE}/workflows`,
            {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    name: workflowName,
                    description: workflowDescription,
                    status: workflowStatus,
                    steps: steps
                })
            }
        );

        // 6. Check the server response.
        const data = await getResponseData(response);
        const workflow = data.workflow;

        if (!workflow?.id) {
            throw new Error(
                "The server did not return the created workflow ID."
            );
        }

        // 7. Display the success message.
        showMessage(
            createWorkflowMessage,
            "Workflow and all three steps created successfully."
        );

        // 8. Clear the workflow builder form.
        createWorkflowForm.reset();

        // 9. Refresh the dashboard.
        await loadWorkflows();

        // 10. Select the newly created workflow.
        if (workflowSelectElement) {
            workflowSelectElement.value = String(workflow.id);

            await loadExecutionHistory(workflow.id);
        }

    } catch (error) {
        console.error("Error creating workflow:", error);

        showMessage(
            createWorkflowMessage,
            error.message,
            true
        );

    } finally {
        // 11. Restore the create button.
        setButtonLoading(
            createWorkflowButton,
            false,
            "Create workflow",
            "Creating workflow..."
        );
    }
}


// ============================================================
// 8. EXECUTE WORKFLOW
// ============================================================

async function executeWorkflow(event) {
    event.preventDefault();

    const workflowId = workflowSelectElement.value;
    const subject = executionSubjectInput.value.trim();
    const body = executionBodyInput.value.trim();

    if (!workflowId) {
        showMessage(
            historyMessageElement,
            "Please select a workflow first.",
            true
        );

        return;
    }

    setButtonLoading(
        executeButton,
        true,
        "Run workflow",
        "Running workflow..."
    );

    try {
        const response = await fetch(
            `${API_BASE}/workflows/${workflowId}/execute`,
            {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    subject: subject,
                    body: body
                })
            }
        );

        const data = await getResponseData(response);

        // Display the execution response inside the existing result box.
        if (executionResultElement) {
            executionResultElement.hidden = false;
        }

        if (executionResultContent) {
            executionResultContent.textContent =
                JSON.stringify(data, null, 2);
        }

        showMessage(
            historyMessageElement,
            "Workflow executed. History has been refreshed."
        );

        await loadExecutionHistory(workflowId);
        await loadTotalExecutionCountFromCurrentWorkflows();

    } catch (error) {
        console.error("Workflow execution failed:", error);

        if (executionResultElement) {
            executionResultElement.hidden = false;
        }

        if (executionResultContent) {
            executionResultContent.textContent = error.message;
        }

    } finally {
        setButtonLoading(
            executeButton,
            false,
            "Run workflow",
            "Running workflow..."
        );
    }
}


// ============================================================
// 9. LOAD EXECUTION HISTORY
// ============================================================

async function loadExecutionHistory(workflowId) {
    if (!workflowId) {
        clearExecutionHistory();
        return;
    }

    try {
        showMessage(historyMessageElement, "Loading execution history...");

        const response = await fetch(
            `${API_BASE}/workflows/${workflowId}/executions`,
            {
                method: "GET",
                credentials: "same-origin"
            }
        );

        const data = await getResponseData(response);
        const executions = data.executions || [];

        displayExecutionHistory(executions);

        showMessage(
            historyMessageElement,
            executions.length
                ? `${executions.length} recent execution(s) found.`
                : "No executions recorded for this workflow yet."
        );

    } catch (error) {
        console.error("Error loading execution history:", error);

        showMessage(
            historyMessageElement,
            error.message,
            true
        );
    }
}


// ============================================================
// 10. DISPLAY EXECUTION HISTORY TABLE
// ============================================================

function displayExecutionHistory(executions) {
    if (!historyTableBody) return;

    historyTableBody.replaceChildren();

    if (executions.length === 0) {
        const row = document.createElement("tr");
        const cell = createTextElement(
            "td",
            "No execution history available."
        );

        cell.colSpan = 4;

        row.appendChild(cell);
        historyTableBody.appendChild(row);

        return;
    }

    executions.forEach(execution => {
        const row = document.createElement("tr");

        const executionId = createTextElement(
            "td",
            execution.id ?? "—"
        );

        const status = createTextElement(
            "td",
            execution.status || "Unknown"
        );

        const started = createTextElement(
            "td",
            formatDate(execution.started_at || execution.created_at)
        );

        const finished = createTextElement(
            "td",
            formatDate(execution.finished_at)
        );

        row.append(
            executionId,
            status,
            started,
            finished
        );

        historyTableBody.appendChild(row);
    });
}


function clearExecutionHistory() {
    if (historyTableBody) {
        historyTableBody.replaceChildren();

        const row = document.createElement("tr");
        const cell = createTextElement(
            "td",
            "Select a workflow to view its history."
        );

        cell.colSpan = 4;

        row.appendChild(cell);
        historyTableBody.appendChild(row);
    }

    showMessage(
        historyMessageElement,
        "Select a workflow to view its history."
    );
}


// ============================================================
// 11. CALCULATE TOTAL EXECUTIONS
// ============================================================

// The executions endpoint returns the latest 50 records.
// Therefore this metric counts the records returned by those
// endpoints, not necessarily every historical execution.

async function loadTotalExecutionCount(workflows) {
    if (!totalExecutionsElement) return;

    try {
        const counts = await Promise.all(
            workflows.map(async workflow => {
                const response = await fetch(
                    `${API_BASE}/workflows/${workflow.id}/executions`,
                    {
                        method: "GET",
                        credentials: "same-origin"
                    }
                );

                const data = await getResponseData(response);

                return (data.executions || []).length;
            })
        );

        const total = counts.reduce(
            (sum, count) => sum + count,
            0
        );

        totalExecutionsElement.textContent = total;

    } catch (error) {
        console.error("Could not calculate execution count:", error);
        totalExecutionsElement.textContent = "—";
    }
}


async function loadTotalExecutionCountFromCurrentWorkflows() {
    try {
        const response = await fetch(`${API_BASE}/workflows`, {
            method: "GET",
            credentials: "same-origin"
        });

        const data = await getResponseData(response);

        await loadTotalExecutionCount(data.workflows || []);

    } catch (error) {
        console.error("Could not refresh execution count:", error);
    }
}


// ============================================================
// 12. WORKFLOW CARD BUTTONS
// ============================================================

if (workflowListElement) {
    workflowListElement.addEventListener("click", event => {

        const testButton = event.target.closest(
            ".test-workflow-button"
        );

        const historyButton = event.target.closest(
            ".view-history-button"
        );

        // Test workflow button
        if (testButton) {
            const workflowId = testButton.dataset.workflowId;

            if (workflowSelectElement) {
                workflowSelectElement.value = workflowId;
            }

            document.getElementById("test-workflow")?.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
        }

        // View history button
        if (historyButton) {
            const workflowId = historyButton.dataset.workflowId;

            if (workflowSelectElement) {
                workflowSelectElement.value = workflowId;
            }

            loadExecutionHistory(workflowId);

            document.getElementById("history")?.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
        }
    });
}


// ============================================================
// 13. EVENT LISTENERS
// ============================================================

// Create workflow
if (createWorkflowForm) {
    createWorkflowForm.addEventListener(
        "submit",
        createWorkflow
    );
}

// Execute workflow
if (executionForm) {
    executionForm.addEventListener(
        "submit",
        executeWorkflow
    );
}

// Change selected workflow
if (workflowSelectElement) {
    workflowSelectElement.addEventListener("change", () => {
        loadExecutionHistory(workflowSelectElement.value);
    });
}

// Refresh workflows
if (refreshWorkflowsButton) {
    refreshWorkflowsButton.addEventListener(
        "click",
        loadWorkflows
    );
}

// Refresh execution history
if (refreshHistoryButton) {
    refreshHistoryButton.addEventListener("click", () => {
        loadExecutionHistory(workflowSelectElement?.value);
    });
}


// ============================================================
// 14. INITIALISE DASHBOARD
// ============================================================

loadWorkflows();
