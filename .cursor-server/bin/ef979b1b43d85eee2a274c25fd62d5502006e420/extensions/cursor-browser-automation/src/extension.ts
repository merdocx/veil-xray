import * as vscode from 'vscode';
import { CursorIDEBrowserLogger } from './logger.js';
import { MCPPrompt, McpProvider, MCPResource, MCPTool } from '@cursor/types';
import { BrowserTools, McpToolResult } from './browserTools.js';
import { generateBrowserUIScript } from './browserUIScript.js';
import { createPatch } from 'diff';

class BrowserAutomationMcpProvider implements McpProvider {
	public readonly id = 'cursor-ide-browser';
	public readonly featureGateName = undefined;
	public readonly featureGatesToCheck = ['use_ide_browser_script'];
	private _featureGates: Record<string, boolean> = {};

	private readonly tools: MCPTool[] = [
		{
			name: 'browser_navigate',
			description: 'Navigate to a URL',
			parameters: JSON.stringify({
				type: 'object',
				properties: {
					url: { type: 'string', description: 'The URL to navigate to' }
				},
				required: ['url']
			})
		},
		{
			name: 'browser_snapshot',
			description: 'Capture accessibility snapshot of the current page, this is better than screenshot',
			parameters: JSON.stringify({
				type: 'object',
				properties: {},
				required: []
			})
		},
		{
			name: 'browser_click',
			description: 'Perform click on a web page',
			parameters: JSON.stringify({
				type: 'object',
				properties: {
					element: { type: 'string', description: 'Human-readable element description used to obtain permission to interact with the element' },
					ref: { type: 'string', description: 'Exact target element reference from the page snapshot' },
					doubleClick: { type: 'boolean', description: 'Whether to perform a double click instead of a single click' },
					button: { type: 'string', description: 'Button to click, defaults to left' },
					modifiers: { type: 'array', items: { type: 'string' }, description: 'Modifier keys to press' }
				},
				required: ['element', 'ref']
			})
		},
		{
			name: 'browser_type',
			description: 'Type text into editable element',
			parameters: JSON.stringify({
				type: 'object',
				properties: {
					element: { type: 'string', description: 'Human-readable element description used to obtain permission to interact with the element' },
					ref: { type: 'string', description: 'Exact target element reference from the page snapshot' },
					text: { type: 'string', description: 'Text to type into the element' },
					submit: { type: 'boolean', description: 'Whether to submit entered text (press Enter after)' },
					slowly: { type: 'boolean', description: 'Whether to type one character at a time. Useful for triggering key handlers in the page. By default entire text is filled in at once.' }
				},
				required: ['element', 'ref', 'text']
			})
		},
		{
			name: 'browser_hover',
			description: 'Hover over element on page',
			parameters: JSON.stringify({
				type: 'object',
				properties: {
					element: { type: 'string', description: 'Human-readable element description used to obtain permission to interact with the element' },
					ref: { type: 'string', description: 'Exact target element reference from the page snapshot' }
				},
				required: ['element', 'ref']
			})
		},
		{
			name: 'browser_select_option',
			description: 'Select an option in a dropdown',
			parameters: JSON.stringify({
				type: 'object',
				properties: {
					element: { type: 'string', description: 'Human-readable element description used to obtain permission to interact with the element' },
					ref: { type: 'string', description: 'Exact target element reference from the page snapshot' },
					values: { type: 'array', items: { type: 'string' }, description: 'Array of values to select in the dropdown. This can be a single value or multiple values.' }
				},
				required: ['element', 'ref', 'values']
			})
		},
		{
			name: 'browser_press_key',
			description: 'Press a key on the keyboard',
			parameters: JSON.stringify({
				type: 'object',
				properties: {
					key: { type: 'string', description: 'Name of the key to press or a character to generate, such as ArrowLeft or a' }
				},
				required: ['key']
			})
		},
		{
			name: 'browser_wait_for',
			description: 'Wait for text to appear or disappear or a specified time to pass',
			parameters: JSON.stringify({
				type: 'object',
				properties: {
					time: { type: 'number', description: 'The time to wait in seconds' },
					text: { type: 'string', description: 'The text to wait for' },
					textGone: { type: 'string', description: 'The text to wait for to disappear' }
				},
				required: []
			})
		},
		{
			name: 'browser_navigate_back',
			description: 'Go back to the previous page',
			parameters: JSON.stringify({
				type: 'object',
				properties: {},
				required: []
			})
		},
		{
			name: 'browser_resize',
			description: 'Resize the browser window',
			parameters: JSON.stringify({
				type: 'object',
				properties: {
					width: { type: 'number', description: 'Width of the browser window' },
					height: { type: 'number', description: 'Height of the browser window' }
				},
				required: ['width', 'height']
			})
		},
		{
			name: 'browser_console_messages',
			description: 'Returns all console messages',
			parameters: JSON.stringify({
				type: 'object',
				properties: {},
				required: []
			})
		},
		{
			name: 'browser_network_requests',
			description: 'Returns all network requests since loading the page',
			parameters: JSON.stringify({
				type: 'object',
				properties: {},
				required: []
			})
		},
		{
			name: 'browser_take_screenshot',
			description: 'Take a screenshot of the current page. You can\'t perform actions based on the screenshot, use browser_snapshot for actions.',
			parameters: JSON.stringify({
				type: 'object',
				properties: {
					type: { type: 'string', description: 'Image format for the screenshot. Default is png.' },
					filename: { type: 'string', description: 'File name to save the screenshot to. Defaults to page-{timestamp}.{png|jpeg} if not specified.' },
					element: { type: 'string', description: 'Description of the element, if taking a screenshot of an element' },
					ref: { type: 'string', description: 'CSS selector for the element, if taking a screenshot of an element' },
					fullPage: { type: 'boolean', description: 'When true, takes a screenshot of the full scrollable page, instead of the currently visible viewport. Cannot be used with element screenshots.' }
				},
				required: []
			})
		}
	];

	async initialize(): Promise<void> {
		CursorIDEBrowserLogger.info('Browser Automation MCP Provider initialized with direct execution');
	}

	async listOfferings(): Promise<{ tools: MCPTool[]; prompts: MCPPrompt[]; resources?: MCPResource[] }> {
		const tools = this._featureGates['use_ide_browser_script'] ? [this.getScriptTool()] : this.tools;
		return {
			tools,
			prompts: [],
			resources: []
		};
	}

	async callTool(toolName: string, args: Record<string, unknown>): Promise<McpToolResult> {
		CursorIDEBrowserLogger.info(`Executing tool: ${toolName} with args: ${JSON.stringify(args)}`);

		try {
			switch (toolName) {
				case 'browser_navigate':
					return await BrowserTools.navigate(args as { url: string })
				case 'browser_snapshot':
					return await BrowserTools.snapshot(args);
				case 'browser_click':
					return await BrowserTools.click(args as any);
				case 'browser_type':
					return await BrowserTools.type(args as any);
				case 'browser_hover':
					return await BrowserTools.hover(args as any);
				case 'browser_select_option':
					return await BrowserTools.selectOption(args as any);
				case 'browser_press_key':
					return await BrowserTools.pressKey(args as { key: string });
				case 'browser_wait_for':
					return await BrowserTools.waitFor(args as any);
				case 'browser_navigate_back':
					return await BrowserTools.goBack(args);
				case 'browser_resize':
					return await BrowserTools.resize(args as { width: number; height: number });
				case 'browser_console_messages':
					return await BrowserTools.consoleMessages(args);
				case 'browser_network_requests':
					return await BrowserTools.networkRequests(args);
				case 'browser_take_screenshot':
					return await BrowserTools.takeScreenshot(args as any);
				case 'browser_script':
					// TODO: cleanup this tool, no longer used / this was an experimental feature
					return { content: [{ type: 'text', text: JSON.stringify(await this.executeScript(args as { actions: { action: string; parameters: Record<string, unknown> }[] })) }] };
				default:
					throw new Error(`Unknown tool: ${toolName}`);
			}
		} catch (error) {
			CursorIDEBrowserLogger.error(`Error executing tool ${toolName}:`, error);
			return { content: [{ type: 'text', text: `Error executing tool ${toolName}: ${error instanceof Error ? error.message : String(error)}` }] };
		}
	}

	async dispose(): Promise<void> {
		CursorIDEBrowserLogger.info('Browser Automation MCP Provider disposed');
	}

	private getScriptTool(): MCPTool {
		const formattedTools = this.tools.
			// We don't want to let the script tool take screen shots or snap shots as we'll be taking diff of snapshots for the user
			filter(tool => tool.name !== 'browser_script' && tool.name !== 'browser_take_screenshot' && tool.name !== 'browser_snapshot').
			map(tool => (`- Action: ${tool.name}\n Description: ${tool.description}\n Parameters: ${JSON.stringify(tool.parameters)}\n`)).join('\n');


		return {
			name: 'browser_script',
			description: `Executes a series of browser automation actions. Available actions: ${formattedTools}`,
			parameters: JSON.stringify({
				type: 'object',
				properties: {
					actions: {
						type: 'array', items: {
							type: 'object', properties: {
								action: { type: 'string', description: 'The action to perform' },
								parameters: { type: 'object', description: 'The parameters for the action' }
							}
						}
					}
				},
				required: ['actions']
			})
		};
	}

	/**
	 * Extract the YAML content from a snapshot text
	 */
	private extractYamlFromSnapshot(snapshotText: string): string {
		const yamlStartMarker = '```yaml\n';
		const yamlEndMarker = '\n```';

		const startIndex = snapshotText.indexOf(yamlStartMarker);
		if (startIndex === -1) return '';

		const contentStart = startIndex + yamlStartMarker.length;
		const endIndex = snapshotText.indexOf(yamlEndMarker, contentStart);

		if (endIndex === -1) return '';

		return snapshotText.substring(contentStart, endIndex);
	}

	/**
	 * Calculate delta between two snapshots using git-diff style algorithm
	 */
	private calculateSnapshotDelta(previousYaml: string, currentYaml: string): {
		added: string[];
		removed: string[];
	} {
		// Generate a unified diff patch
		const patch = createPatch(
			'snapshot',
			previousYaml,
			currentYaml,
			'previous',
			'current',
			{ context: 3 }
		);

		// Parse the patch to extract added/removed lines
		const added: string[] = [];
		const removed: string[] = [];

		// Split patch into lines and process
		const patchLines = patch.split('\n');
		let inHunk = false;

		for (const line of patchLines) {
			// Skip header lines
			if (line.startsWith('---') || line.startsWith('+++') || line.startsWith('@@')) {
				inHunk = line.startsWith('@@');
				continue;
			}

			if (inHunk && line.length > 0) {
				const prefix = line[0];
				const content = line.substring(1).trim(); // Remove diff prefix (+/-/space)

				if (prefix === '+' && content) {
					added.push(content);
				} else if (prefix === '-' && content) {
					removed.push(content);
				}
			}
		}

		return { added, removed, };
	}

	setFeatureGates(featureGates: Record<string, boolean>): void {
		this._featureGates = featureGates;
	}

	private async executeScript(args: { actions: { action: string; parameters: Record<string, unknown> }[] }): Promise<unknown> {
		const { actions } = args;
		const listOfToolCalls = actions.map(action => ({
			toolName: action.action,
			parameters: action.parameters
		}));

		const results = [];

		// Take initial snapshot
		let previousSnapshot: { content: { type: 'text'; text: string }[] } | null = null;
		let previousYaml: string | null = null;

		// Execute each action and track deltas
		for (const toolCall of listOfToolCalls) {
			try {
				// Execute the action
				const actionResult = await this.callTool(toolCall.toolName, toolCall.parameters);

				// Take a new snapshot after the action
				const currentSnapshot = await BrowserTools.snapshot({}) as { content: { type: 'text'; text: string }[] };
				const currentYaml = this.extractYamlFromSnapshot(currentSnapshot.content[0]?.text || '');

				if (previousYaml) {
					// Calculate delta
					const delta = this.calculateSnapshotDelta(previousYaml, currentYaml);

					// Add result with delta
					results.push({
						action: toolCall.toolName,
						parameters: toolCall.parameters,
						result: scrubSnapshotFromResult(actionResult),
						delta: {
							added: delta.added,
							removed: delta.removed,
							summary: {
								addedCount: delta.added.length,
								removedCount: delta.removed.length
							}
						}
					});
				} else if (toolCall.toolName === 'browser_snapshot' || toolCall.toolName === 'browser_navigate') {
					// The initial tool call made is a browser snapshot or navigate, so no need to add in the results as it's
					// both will return a snapshot of the page
					results.push({
						action: 'initial_state',
						snapshot: currentSnapshot,
					});
				} else {
					results.push({
						action: 'initial_state',
						snapshot: currentSnapshot,
					});
					// The initial tool call was not a browser snapshot, so we need to add in the results
					results.push({
						action: toolCall.toolName,
						parameters: toolCall.parameters,
						result: scrubSnapshotFromResult(actionResult),
					});
				}
				// Update previous snapshot for next iteration
				previousSnapshot = currentSnapshot;
				previousYaml = currentYaml;

			} catch (error) {
				results.push({
					action: toolCall.toolName,
					parameters: toolCall.parameters,
					error: error instanceof Error ? error.message : String(error),
					delta: {
						added: [],
						removed: [],
						summary: {
							addedCount: 0,
							changedCount: 0,
							removedCount: 0
						}
					}
				});
			}
		}

		return {
			results,
			success: true,
			summary: {
				totalActions: actions.length,
				successfulActions: results.filter(r => !r.error).length - 1, // Subtract initial state
				failedActions: results.filter(r => r.error).length
			}
		};
	}
}

let mcpProvider: BrowserAutomationMcpProvider | undefined;

async function injectBrowserUIScript(): Promise<void> {
	try {
		const script = generateBrowserUIScript('browser-tab-id');
		await vscode.commands.executeCommand('cursor.browserView.executeJavaScript', script);
		CursorIDEBrowserLogger.info('Browser UI script injected successfully');
	} catch (error) {
		CursorIDEBrowserLogger.error('Failed to inject browser UI script:', error);
	}
}

export async function activate(context: vscode.ExtensionContext) {
	CursorIDEBrowserLogger.init();
	CursorIDEBrowserLogger.info('Cursor Browser Automation extension activated');

	mcpProvider = new BrowserAutomationMcpProvider();
	await mcpProvider.initialize();

	const mcpDisposable = vscode.cursor.registerMcpProvider(mcpProvider);
	context.subscriptions.push(mcpDisposable);

	// Register command to re-inject UI script
	const reinjectCommand = vscode.commands.registerCommand(
		'cursor.browserAutomation.reinjectUIScript',
		injectBrowserUIScript
	);
	context.subscriptions.push(reinjectCommand);

	// Initial injection attempt
	// Note: This may fail if browser view hasn't been created yet, which is fine
	// The script will be injected when BrowserEditorContent calls the command
	injectBrowserUIScript().catch(() => {
		// Silently ignore - browser view may not exist yet
	});
}

export async function deactivate() {
	if (mcpProvider) {
		await mcpProvider.dispose();
		mcpProvider = undefined;
	}
}

function scrubSnapshotFromResult(result: unknown): unknown {
	// Handle null/undefined
	if (result === null || result === undefined) {
		return result;
	}

	// Handle arrays - recursively process each element
	if (Array.isArray(result)) {
		return result.map(item => scrubSnapshotFromResult(item));
	}

	// Handle objects
	if (typeof result === 'object' && result !== null) {
		const scrubbed: Record<string, unknown> = {};

		for (const [key, value] of Object.entries(result)) {
			// Skip any key named "snapshot" (recursively remove it)
			if (key === 'snapshot') {
				continue; // Don't include this key at all
			}
			// Recursively process all other values
			else {
				scrubbed[key] = scrubSnapshotFromResult(value);
			}
		}

		return scrubbed;
	}

	// Return primitive values as-is
	return result;
}
