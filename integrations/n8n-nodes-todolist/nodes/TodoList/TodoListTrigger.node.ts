import type {
	IHookFunctions,
	INodeType,
	INodeTypeDescription,
	IWebhookFunctions,
	IWebhookResponseData,
} from 'n8n-workflow';

export class TodoListTrigger implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'TODOlist Trigger',
		name: 'todoListTrigger',
		icon: 'file:todolist.svg',
		group: ['trigger'],
		version: 1,
		description:
			'Starts the workflow when a TODOlist webhook fires (task created/updated/completed/…)',
		defaults: { name: 'TODOlist Trigger' },
		inputs: [],
		outputs: ['main'],
		credentials: [{ name: 'todoListApi', required: true }],
		webhooks: [
			{
				name: 'default',
				httpMethod: 'POST',
				responseMode: 'onReceived',
				path: 'todolist',
			},
		],
		properties: [
			{
				displayName: 'Events',
				name: 'events',
				type: 'multiOptions',
				required: true,
				default: ['task_created'],
				options: [
					{ name: 'Task Created', value: 'task_created' },
					{ name: 'Task Updated', value: 'task_updated' },
					{ name: 'Task Completed', value: 'task_completed' },
					{ name: 'Task Deleted', value: 'task_deleted' },
					{ name: 'Comment Added', value: 'comment_added' },
					{ name: 'Sprint Started', value: 'sprint_started' },
					{ name: 'Sprint Closed', value: 'sprint_closed' },
				],
			},
		],
	};

	webhookMethods = {
		default: {
			// Al activar el workflow se registra un OutgoingWebhook en
			// TODOlist apuntando a la URL de n8n; al desactivar se borra.
			async checkExists(this: IHookFunctions): Promise<boolean> {
				const staticData = this.getWorkflowStaticData('node');
				return !!staticData.webhookId;
			},
			async create(this: IHookFunctions): Promise<boolean> {
				const webhookUrl = this.getNodeWebhookUrl('default');
				const events = this.getNodeParameter('events') as string[];
				const { baseUrl } = (await this.getCredentials('todoListApi')) as {
					baseUrl: string;
				};
				const resp = (await this.helpers.httpRequest({
					method: 'POST',
					url: `${baseUrl.replace(/\/$/, '')}/api/outgoing-webhooks/`,
					headers: {
						Authorization: `ApiKey ${(await this.getCredentials('todoListApi')).apiKey}`,
						'Content-Type': 'application/json',
					},
					body: { url: webhookUrl, events, is_active: true },
					json: true,
				})) as { id: number };
				this.getWorkflowStaticData('node').webhookId = resp.id;
				return true;
			},
			async delete(this: IHookFunctions): Promise<boolean> {
				const staticData = this.getWorkflowStaticData('node');
				const id = staticData.webhookId;
				if (!id) return true;
				const { baseUrl, apiKey } = (await this.getCredentials(
					'todoListApi',
				)) as { baseUrl: string; apiKey: string };
				try {
					await this.helpers.httpRequest({
						method: 'DELETE',
						url: `${baseUrl.replace(/\/$/, '')}/api/outgoing-webhooks/${id}/`,
						headers: { Authorization: `ApiKey ${apiKey}` },
						json: true,
					});
				} catch {
					// 404 = ya borrado; otros errores no deben bloquear el deactivate
				}
				delete staticData.webhookId;
				return true;
			},
		},
	};

	async webhook(this: IWebhookFunctions): Promise<IWebhookResponseData> {
		return {
			workflowData: [
				this.helpers.returnJsonArray(this.getBodyData() as any),
			],
		};
	}
}
