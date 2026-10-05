import type {
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
	IHttpRequestMethods,
} from 'n8n-workflow';

export class TodoList implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'TODOlist',
		name: 'todoList',
		icon: 'file:todolist.svg',
		group: ['transform'],
		version: 1,
		subtitle: '={{$parameter["operation"] + ": " + $parameter["resource"]}}',
		description: 'Create, read, update and complete tasks in TODOlist',
		defaults: { name: 'TODOlist' },
		inputs: ['main'],
		outputs: ['main'],
		credentials: [{ name: 'todoListApi', required: true }],
		requestDefaults: {
			baseURL: '={{$credentials.baseUrl}}',
			headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
		},
		properties: [
			{
				displayName: 'Resource',
				name: 'resource',
				type: 'options',
				noDataExpression: true,
				options: [
					{ name: 'Task', value: 'task' },
					{ name: 'Project', value: 'project' },
					{ name: 'Comment', value: 'comment' },
				],
				default: 'task',
			},
			// ---- Task operations ----
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: { show: { resource: ['task'] } },
				options: [
					{ name: 'Create', value: 'create', action: 'Create a task' },
					{ name: 'Delete', value: 'delete', action: 'Delete a task' },
					{ name: 'Get', value: 'get', action: 'Get a task' },
					{ name: 'Get Many', value: 'getAll', action: 'Get many tasks' },
					{ name: 'Mark Complete', value: 'complete', action: 'Mark a task as completed' },
					{ name: 'Update', value: 'update', action: 'Update a task' },
				],
				default: 'getAll',
			},
			// ---- Project operations ----
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: { show: { resource: ['project'] } },
				options: [{ name: 'Get Many', value: 'getAll', action: 'Get many projects' }],
				default: 'getAll',
			},
			// ---- Comment operations ----
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: { show: { resource: ['comment'] } },
				options: [{ name: 'Create', value: 'create', action: 'Add a comment to a task' }],
				default: 'create',
			},

			// ---- Shared fields ----
			{
				displayName: 'Task ID',
				name: 'taskId',
				type: 'number',
				required: true,
				default: 0,
				displayOptions: {
					show: {
						resource: ['task'],
						operation: ['get', 'update', 'delete', 'complete'],
					},
				},
			},
			{
				displayName: 'Task ID',
				name: 'taskId',
				type: 'number',
				required: true,
				default: 0,
				displayOptions: { show: { resource: ['comment'], operation: ['create'] } },
			},
			{
				displayName: 'Title',
				name: 'title',
				type: 'string',
				required: true,
				default: '',
				displayOptions: { show: { resource: ['task'], operation: ['create'] } },
			},
			{
				displayName: 'Body',
				name: 'body',
				type: 'string',
				required: true,
				default: '',
				displayOptions: { show: { resource: ['comment'], operation: ['create'] } },
			},
			{
				displayName: 'Additional Fields',
				name: 'additionalFields',
				type: 'collection',
				placeholder: 'Add Field',
				default: {},
				displayOptions: { show: { resource: ['task'], operation: ['create', 'update'] } },
				options: [
					{ displayName: 'Title', name: 'title', type: 'string', default: '' },
					{ displayName: 'Description', name: 'description', type: 'string', default: '' },
					{
						displayName: 'State',
						name: 'state',
						type: 'options',
						options: [
							{ name: 'Pending', value: 'pending' },
							{ name: 'In Progress', value: 'in_progress' },
							{ name: 'Blocked', value: 'blocked' },
							{ name: 'Review', value: 'review' },
							{ name: 'Completed', value: 'completed' },
							{ name: 'Cancelled', value: 'cancelled' },
						],
						default: 'pending',
					},
					{
						displayName: 'Priority',
						name: 'priority',
						type: 'number',
						default: 3,
						description: '0 (urgent) to 5 (lowest)',
					},
					{
						displayName: 'Due Date',
						name: 'due_date',
						type: 'dateTime',
						default: '',
					},
					{ displayName: 'Project ID', name: 'project', type: 'number', default: 0 },
				],
			},
			{
				displayName: 'Filters',
				name: 'filters',
				type: 'collection',
				placeholder: 'Add Filter',
				default: {},
				displayOptions: { show: { resource: ['task'], operation: ['getAll'] } },
				options: [
					{ displayName: 'Project ID', name: 'project', type: 'number', default: 0 },
					{
						displayName: 'State',
						name: 'state',
						type: 'options',
						options: [
							{ name: 'Pending', value: 'pending' },
							{ name: 'In Progress', value: 'in_progress' },
							{ name: 'Blocked', value: 'blocked' },
							{ name: 'Review', value: 'review' },
							{ name: 'Completed', value: 'completed' },
							{ name: 'Cancelled', value: 'cancelled' },
						],
						default: 'pending',
					},
					{ displayName: 'Search', name: 'search', type: 'string', default: '' },
					{ displayName: 'Limit', name: 'limit', type: 'number', default: 50 },
				],
			},
		],
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnData: INodeExecutionData[] = [];
		const resource = this.getNodeParameter('resource', 0) as string;
		const operation = this.getNodeParameter('operation', 0) as string;

		for (let i = 0; i < items.length; i++) {
			let response: any;
			const base = (this.getCredentials('todoListApi', i) as { baseUrl: string })
				.baseUrl.replace(/\/$/, '');

			const call = (
				method: IHttpRequestMethods,
				path: string,
				body?: object,
				qs?: object,
			) =>
				this.helpers.httpRequestWithAuthentication.call(this, 'todoListApi', {
					method,
					url: `${base}/api${path}`,
					body,
					qs,
					json: true,
				});

			if (resource === 'project' && operation === 'getAll') {
				response = await call('GET', '/projects/');
			} else if (resource === 'task') {
				if (operation === 'getAll') {
					const filters = this.getNodeParameter('filters', i) as Record<string, any>;
					const qs: Record<string, any> = {};
					for (const k of ['project', 'state', 'search', 'limit']) {
						if (filters[k] !== undefined && filters[k] !== '' && filters[k] !== 0)
							qs[k === 'limit' ? 'page_size' : k] = filters[k];
					}
					response = await call('GET', '/tasks/', undefined, qs);
				} else if (operation === 'get') {
					const id = this.getNodeParameter('taskId', i);
					response = await call('GET', `/tasks/${id}/`);
				} else if (operation === 'create') {
					const title = this.getNodeParameter('title', i) as string;
					const extra = this.getNodeParameter('additionalFields', i) as Record<string, any>;
					const body: Record<string, any> = { title, ...extra };
					if (body.project === 0) delete body.project;
					if (body.due_date === '') delete body.due_date;
					response = await call('POST', '/tasks/', body);
				} else if (operation === 'update') {
					const id = this.getNodeParameter('taskId', i);
					const extra = this.getNodeParameter('additionalFields', i) as Record<string, any>;
					const body: Record<string, any> = { ...extra };
					for (const k of Object.keys(body)) {
						if (body[k] === '' || body[k] === 0) delete body[k];
					}
					response = await call('PATCH', `/tasks/${id}/`, body);
				} else if (operation === 'complete') {
					const id = this.getNodeParameter('taskId', i);
					response = await call('PATCH', `/tasks/${id}/`, { state: 'completed' });
				} else if (operation === 'delete') {
					const id = this.getNodeParameter('taskId', i);
					response = await call('DELETE', `/tasks/${id}/`);
				}
			} else if (resource === 'comment' && operation === 'create') {
				const id = this.getNodeParameter('taskId', i);
				const body = this.getNodeParameter('body', i) as string;
				response = await call('POST', `/tasks/${id}/comments/`, { body });
			}

			const rows = Array.isArray(response?.results) ? response.results : response;
			if (Array.isArray(rows)) {
				for (const row of rows) returnData.push({ json: row });
			} else {
				returnData.push({ json: rows ?? { success: true } });
			}
		}
		return [returnData];
	}
}
