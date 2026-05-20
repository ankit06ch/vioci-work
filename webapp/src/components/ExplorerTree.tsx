import { useMemo, useState } from 'react'
import type { ProjectMeta, SchemaFolder } from '../api/types'
import {
  SCHEMA_EXPORT_FILES,
  type ExplorerSchemaFileId,
} from '../lib/schemaExports'

type Props = {
  folders: SchemaFolder[]
  projects: ProjectMeta[]
  selectedProjectId: string | null
  selectedSchemaFile: ExplorerSchemaFileId | null
  selectedFolderId: string | null
  schemaExpanded: Record<string, boolean>
  onToggleSchemaExpand: (projectId: string) => void
  onSelectProject: (id: string) => void
  onSelectSchemaFile: (projectId: string, file: ExplorerSchemaFileId) => void
  onSelectFolder: (id: string | null) => void
  onOpenProject: (id: string) => void
  onCreateFolder: (name: string, parentId: string | null) => void
  onDeleteFolder: (folderId: string) => void
  onMoveProject: (projectId: string, folderId: string | null) => void
  onUploadToFolder: (folderId: string | null, files: FileList) => void
  statusClass: (p: ProjectMeta) => string
  statusLabel: (p: ProjectMeta) => string
  creatingFolder: boolean
  onCancelCreateFolder: () => void
}

type DropTarget = 'root' | string

type ProjectNodeProps = {
  project: ProjectMeta
  padLeft: number
  selectedProjectId: string | null
  selectedSchemaFile: ExplorerSchemaFileId | null
  schemaExpanded: boolean
  onToggleSchemaExpand: () => void
  onSelectProject: (id: string) => void
  onSelectSchemaFile: (projectId: string, file: ExplorerSchemaFileId) => void
  onOpenProject: (id: string) => void
  statusClassFn: (p: ProjectMeta) => string
  statusLabelFn: (p: ProjectMeta) => string
}

function ExplorerProjectNode({
  project: p,
  padLeft,
  selectedProjectId,
  selectedSchemaFile,
  schemaExpanded,
  onToggleSchemaExpand,
  onSelectProject,
  onSelectSchemaFile,
  onOpenProject,
  statusClassFn,
  statusLabelFn,
}: ProjectNodeProps) {
  const hasSchema = p.has_schema_registry ?? false
  const showExports = hasSchema || (p.parse_status === 'done' && p.has_diagram)

  return (
    <li className="explorer-project-node">
      <div className="explorer-tree-row" style={{ paddingLeft: `${padLeft}px` }}>
        {showExports ? (
          <button
            type="button"
            className="explorer-schema-chevron"
            aria-expanded={schemaExpanded}
            title={schemaExpanded ? 'Collapse schema exports' : 'Expand schema exports'}
            onClick={(e) => {
              e.stopPropagation()
              onToggleSchemaExpand()
            }}
          >
            {schemaExpanded ? '▾' : '▸'}
          </button>
        ) : (
          <span className="explorer-schema-chevron spacer" />
        )}
        <button
          type="button"
          role="option"
          aria-selected={selectedProjectId === p.id && !selectedSchemaFile}
          className={`explorer-file ${selectedProjectId === p.id && !selectedSchemaFile ? 'explorer-file-active' : ''}`}
          onClick={() => onSelectProject(p.id)}
          onDoubleClick={() => onOpenProject(p.id)}
          draggable
          onDragStart={(e) => {
            e.dataTransfer.setData('text/project-id', p.id)
            e.dataTransfer.effectAllowed = 'move'
          }}
        >
          <span className="explorer-file-icon">📄</span>
          <span className="explorer-file-name" title={p.name}>
            {p.name}
          </span>
          <span className={`explorer-file-badge ${statusClassFn(p)}`}>{statusLabelFn(p)}</span>
        </button>
      </div>
      {showExports && schemaExpanded ? (
        <ul className="explorer-schema-children" role="group" aria-label="Schema exports">
          {SCHEMA_EXPORT_FILES.map((f) => (
            <li key={f.id}>
              <button
                type="button"
                className={`explorer-schema-file ${
                  selectedProjectId === p.id && selectedSchemaFile === f.id
                    ? 'explorer-file-active'
                    : ''
                }`}
                style={{ paddingLeft: `${padLeft + 22}px` }}
                onClick={() => onSelectSchemaFile(p.id, f.id)}
              >
                <span className="explorer-file-icon">{f.icon}</span>
                <span className="explorer-file-name">{f.label}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  )
}

function handleDrop(
  e: React.DragEvent,
  target: DropTarget,
  onMoveProject: (projectId: string, folderId: string | null) => void,
  onUploadToFolder: (folderId: string | null, files: FileList) => void,
) {
  e.preventDefault()
  e.stopPropagation()
  const folderId = target === 'root' ? null : target
  if (e.dataTransfer.files?.length) {
    onUploadToFolder(folderId, e.dataTransfer.files)
    return
  }
  const pid = e.dataTransfer.getData('text/project-id')
  if (pid) onMoveProject(pid, folderId)
}

function handleDragOver(e: React.DragEvent) {
  e.preventDefault()
  e.stopPropagation()
  if (e.dataTransfer.types.includes('Files')) {
    e.dataTransfer.dropEffect = 'copy'
  } else {
    e.dataTransfer.dropEffect = 'move'
  }
}

type FolderBranchProps = {
  folder: SchemaFolder
  childFolders: SchemaFolder[]
  childProjects: ProjectMeta[]
  allFolders: SchemaFolder[]
  allProjects: ProjectMeta[]
  depth: number
  selectedProjectId: string | null
  selectedSchemaFile: ExplorerSchemaFileId | null
  selectedFolderId: string | null
  schemaExpanded: Record<string, boolean>
  onToggleSchemaExpand: (projectId: string) => void
  dropHighlight: DropTarget | null
  onSelectProject: (id: string) => void
  onSelectSchemaFile: (projectId: string, file: ExplorerSchemaFileId) => void
  onSelectFolder: (id: string | null) => void
  onOpenProject: (id: string) => void
  onCreateFolder: (name: string, parentId: string | null) => void
  onDeleteFolder: (folderId: string) => void
  onMoveProject: (projectId: string, folderId: string | null) => void
  onUploadToFolder: (folderId: string | null, files: FileList) => void
  onDropHighlight: (target: DropTarget | null) => void
  statusClassFn: (p: ProjectMeta) => string
  statusLabelFn: (p: ProjectMeta) => string
}

function FolderBranch({
  folder,
  childFolders,
  childProjects,
  allFolders,
  allProjects,
  depth,
  selectedProjectId,
  selectedSchemaFile,
  selectedFolderId,
  schemaExpanded,
  onToggleSchemaExpand,
  dropHighlight,
  onSelectProject,
  onSelectSchemaFile,
  onSelectFolder,
  onOpenProject,
  onCreateFolder,
  onDeleteFolder,
  onMoveProject,
  onUploadToFolder,
  onDropHighlight,
  statusClassFn,
  statusLabelFn,
}: FolderBranchProps) {
  const [open, setOpen] = useState(true)
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const pad = { paddingLeft: `${12 + depth * 14}px` }

  const submitSubfolder = () => {
    const n = newName.trim()
    if (!n) return
    onCreateFolder(n, folder.id)
    setNewName('')
    setCreating(false)
    setOpen(true)
  }

  return (
    <li className="explorer-tree-branch">
      <div className="explorer-tree-row" style={pad}>
        <button
          type="button"
          className={`explorer-folder ${selectedFolderId === folder.id ? 'explorer-folder-active' : ''} ${dropHighlight === folder.id ? 'explorer-drop-target' : ''}`}
          onClick={() => {
            onSelectFolder(folder.id)
            setOpen((o) => !o)
          }}
          onDragEnter={() => onDropHighlight(folder.id)}
          onDragLeave={() => onDropHighlight(null)}
          onDragOver={handleDragOver}
          onDrop={(e) => {
            handleDrop(e, folder.id, onMoveProject, onUploadToFolder)
            onDropHighlight(null)
          }}
        >
          <span className="explorer-chevron">{open ? '▾' : '▸'}</span>
          <span className="explorer-folder-icon">📁</span>
          <span className="explorer-folder-name">{folder.name}</span>
        </button>
        <button
          type="button"
          className="explorer-tree-action"
          title="New subfolder"
          onClick={() => {
            onSelectFolder(folder.id)
            setCreating(true)
            setOpen(true)
          }}
        >
          +
        </button>
        <button
          type="button"
          className="explorer-tree-action"
          title="Delete folder (must be empty)"
          onClick={() => {
            if (confirm(`Delete folder "${folder.name}"?`)) onDeleteFolder(folder.id)
          }}
        >
          ×
        </button>
      </div>

      {creating ? (
        <form
          className="explorer-new-folder"
          style={{ paddingLeft: `${24 + depth * 14}px` }}
          onSubmit={(e) => {
            e.preventDefault()
            submitSubfolder()
          }}
        >
          <input
            className="auth-input"
            autoFocus
            placeholder="Subfolder name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <button type="submit" className="btn btn-primary">
            Add
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => setCreating(false)}>
            Cancel
          </button>
        </form>
      ) : null}

      {open && (
        <ul className="explorer-tree-children">
          {childFolders.map((cf) => (
            <FolderBranch
              key={cf.id}
              folder={cf}
              childFolders={allFolders.filter((f) => f.parent_id === cf.id)}
              childProjects={allProjects.filter((p) => p.folder_id === cf.id)}
              allFolders={allFolders}
              allProjects={allProjects}
              depth={depth + 1}
              selectedProjectId={selectedProjectId}
              selectedSchemaFile={selectedSchemaFile}
              selectedFolderId={selectedFolderId}
              schemaExpanded={schemaExpanded}
              onToggleSchemaExpand={onToggleSchemaExpand}
              dropHighlight={dropHighlight}
              onSelectProject={onSelectProject}
              onSelectSchemaFile={onSelectSchemaFile}
              onSelectFolder={onSelectFolder}
              onOpenProject={onOpenProject}
              onCreateFolder={onCreateFolder}
              onDeleteFolder={onDeleteFolder}
              onMoveProject={onMoveProject}
              onUploadToFolder={onUploadToFolder}
              onDropHighlight={onDropHighlight}
              statusClassFn={statusClassFn}
              statusLabelFn={statusLabelFn}
            />
          ))}
          {childProjects.map((p) => (
            <ExplorerProjectNode
              key={p.id}
              project={p}
              padLeft={28 + depth * 14}
              selectedProjectId={selectedProjectId}
              selectedSchemaFile={selectedSchemaFile}
              schemaExpanded={!!schemaExpanded[p.id]}
              onToggleSchemaExpand={() => onToggleSchemaExpand(p.id)}
              onSelectProject={onSelectProject}
              onSelectSchemaFile={onSelectSchemaFile}
              onOpenProject={onOpenProject}
              statusClassFn={statusClassFn}
              statusLabelFn={statusLabelFn}
            />
          ))}
        </ul>
      )}
    </li>
  )
}

export function ExplorerTree({
  folders,
  projects,
  selectedProjectId,
  selectedSchemaFile,
  selectedFolderId,
  schemaExpanded,
  onToggleSchemaExpand,
  onSelectProject,
  onSelectSchemaFile,
  onSelectFolder,
  onOpenProject,
  onCreateFolder,
  onDeleteFolder,
  onMoveProject,
  onUploadToFolder,
  statusClass,
  statusLabel,
  creatingFolder,
  onCancelCreateFolder,
}: Props) {
  const [rootOpen, setRootOpen] = useState(true)
  const [newFolderName, setNewFolderName] = useState('')
  const [dropHighlight, setDropHighlight] = useState<DropTarget | null>(null)

  const rootFolders = useMemo(
    () => folders.filter((f) => !f.parent_id).sort((a, b) => a.name.localeCompare(b.name)),
    [folders],
  )
  const rootProjects = useMemo(
    () => projects.filter((p) => !p.folder_id).sort((a, b) => a.name.localeCompare(b.name)),
    [projects],
  )

  return (
    <div className="explorer-tree-inner">
      <button
        type="button"
        className={`explorer-folder explorer-root ${selectedFolderId === null ? 'explorer-folder-active' : ''} ${dropHighlight === 'root' ? 'explorer-drop-target' : ''}`}
        onClick={() => {
          onSelectFolder(null)
          setRootOpen((o) => !o)
        }}
        onDragEnter={() => setDropHighlight('root')}
        onDragLeave={() => setDropHighlight(null)}
        onDragOver={handleDragOver}
        onDrop={(e) => {
          handleDrop(e, 'root', onMoveProject, onUploadToFolder)
          setDropHighlight(null)
        }}
      >
        <span className="explorer-chevron">{rootOpen ? '▾' : '▸'}</span>
        <span className="explorer-folder-icon">📁</span>
        <span>schematics</span>
      </button>

      {rootOpen && (
        <ul className="explorer-file-list explorer-tree-root" role="listbox">
          {rootFolders.map((f) => (
            <FolderBranch
              key={f.id}
              folder={f}
              childFolders={folders.filter((x) => x.parent_id === f.id)}
              childProjects={projects.filter((p) => p.folder_id === f.id)}
              allFolders={folders}
              allProjects={projects}
              depth={0}
              selectedProjectId={selectedProjectId}
              selectedSchemaFile={selectedSchemaFile}
              selectedFolderId={selectedFolderId}
              schemaExpanded={schemaExpanded}
              onToggleSchemaExpand={onToggleSchemaExpand}
              dropHighlight={dropHighlight}
              onSelectProject={onSelectProject}
              onSelectSchemaFile={onSelectSchemaFile}
              onSelectFolder={onSelectFolder}
              onOpenProject={onOpenProject}
              onCreateFolder={onCreateFolder}
              onDeleteFolder={onDeleteFolder}
              onMoveProject={onMoveProject}
              onUploadToFolder={onUploadToFolder}
              onDropHighlight={setDropHighlight}
              statusClassFn={statusClass}
              statusLabelFn={statusLabel}
            />
          ))}

          {rootProjects.map((p) => (
            <ExplorerProjectNode
              key={p.id}
              project={p}
              padLeft={28}
              selectedProjectId={selectedProjectId}
              selectedSchemaFile={selectedSchemaFile}
              schemaExpanded={!!schemaExpanded[p.id]}
              onToggleSchemaExpand={() => onToggleSchemaExpand(p.id)}
              onSelectProject={onSelectProject}
              onSelectSchemaFile={onSelectSchemaFile}
              onOpenProject={onOpenProject}
              statusClassFn={statusClass}
              statusLabelFn={statusLabel}
            />
          ))}

          {!rootFolders.length && !rootProjects.length ? (
            <li className="explorer-empty muted">Drop files on a folder to upload</li>
          ) : null}
        </ul>
      )}

      {creatingFolder ? (
        <form
          className="explorer-new-folder"
          onSubmit={(e) => {
            e.preventDefault()
            const n = newFolderName.trim()
            if (!n) return
            onCreateFolder(n, selectedFolderId)
            setNewFolderName('')
            onCancelCreateFolder()
            setRootOpen(true)
          }}
        >
          <input
            className="auth-input"
            autoFocus
            placeholder={selectedFolderId ? 'Subfolder name' : 'Folder name'}
            value={newFolderName}
            onChange={(e) => setNewFolderName(e.target.value)}
          />
          <button type="submit" className="btn btn-primary">
            Create
          </button>
          <button type="button" className="btn btn-ghost" onClick={onCancelCreateFolder}>
            Cancel
          </button>
        </form>
      ) : null}
    </div>
  )
}
