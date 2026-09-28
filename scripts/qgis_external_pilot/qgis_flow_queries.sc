import java.nio.charset.StandardCharsets
import java.nio.file.Files

import io.shiftleft.codepropertygraph.generated.nodes

@main def main(
  cpgFile: String,
  outputPath: String,
  recordId: String,
  sourceSha256: String,
  corpusKind: String,
  sourcePath: String
) = {
  import io.joern.dataflowengineoss.language.*

  val OperatorId = "^[A-Za-z][A-Za-z0-9_]*:[^\\s]+$".r
  val ApiSourceNames = Set(
    "geometry",
    "buffer",
    "centroid",
    "intersection",
    "difference",
    "combine",
    "simplify",
    "transform",
    "makeValid",
    "boundingBox"
  )
  val ApiTransformNames = ApiSourceNames - "geometry"
  val ApiTerminalNames = Set("setGeometry", "addFeature", "addFeatures", "writeAsVectorFormatV3")

  def unquote(code: String): String = {
    val trimmed = code.trim
    if (trimmed.length >= 2 && Set('\'', '"').contains(trimmed.head) && trimmed.last == trimmed.head) {
      trimmed.substring(1, trimmed.length - 1)
    } else {
      trimmed
    }
  }

  def isOperatorId(code: String): Boolean = OperatorId.matches(unquote(code))

  def nodeJson(node: nodes.AstNode, sourcePath: String): ujson.Value = {
    ujson.Obj(
      "node_id" -> ujson.Num(node.id.toDouble),
      "label" -> ujson.Str(node.getClass.getSimpleName.toUpperCase),
      "code" -> ujson.Str(node.code),
      "source_path" -> ujson.Str(sourcePath),
      "line" -> ujson.Num(node.lineNumber.getOrElse(1).toDouble),
      "column" -> ujson.Num(node.columnNumber.getOrElse(0).toDouble)
    )
  }

  def nodeIds(items: Seq[nodes.AstNode]): ujson.Value = {
    ujson.Arr.from(items.map(node => ujson.Num(node.id.toDouble)))
  }

  def pathsJson(paths: Seq[Seq[nodes.AstNode]]): ujson.Value = {
    ujson.Arr.from(paths.map(path => nodeIds(path)))
  }

  def isSimplePath(path: Seq[nodes.AstNode]): Boolean = {
    path.size >= 2 && path.map(_.id).distinct.size == path.size
  }

  def queryJson(
    queryId: String,
    status: String,
    paths: Seq[Seq[nodes.AstNode]],
    controls: Seq[nodes.AstNode],
    terminals: Seq[nodes.AstNode],
    evidenceKinds: Seq[String]
  ): ujson.Value = {
    val sources = paths.flatMap(_.headOption).distinctBy(_.id).sortBy(_.id)
    val sinks = paths.flatMap(_.lastOption).distinctBy(_.id).sortBy(_.id)
    ujson.Obj(
      "query_id" -> ujson.Str(queryId),
      "status" -> ujson.Str(status),
      "source_node_ids" -> nodeIds(sources),
      "sink_node_ids" -> nodeIds(sinks),
      "flow_paths" -> pathsJson(paths),
      "control_path_node_ids" -> nodeIds(controls.sortBy(_.id)),
      "terminal_node_ids" -> nodeIds(terminals.sortBy(_.id)),
      "evidence_kinds" -> ujson.Arr.from(evidenceKinds.sorted.distinct.map(ujson.Str(_))),
      "error" -> ujson.Str("")
    )
  }

  importCpg(cpgFile)

  require(Set("processing", "api").contains(corpusKind), s"unsupported corpus kind: $corpusKind")

  def logicalProcessingCalls = cpg.call.filter { call =>
    call.argument.l.collect {
      case literal: nodes.Literal if literal.argumentIndex == 1 => literal.code
    }.exists(isOperatorId)
  }
  def directProcessingCalls = cpg.call.filter { call =>
    call.name == "run" && call.code.trim.startsWith("processing.run(")
  }
  def operatorLiterals = cpg.literal.filter(literal => isOperatorId(literal.code))

  val operatorPaths = logicalProcessingCalls.argument
    .reachableByFlows(operatorLiterals)
    .l
    .map(_.elements.collect { case node: nodes.AstNode => node })
    .filter(isSimplePath)
  val helperPaths = directProcessingCalls.argument
    .reachableByFlows(operatorLiterals)
    .l
    .map(_.elements.collect { case node: nodes.AstNode => node })
    .filter(isSimplePath)
  val parameterPaths = directProcessingCalls.argument(2)
    .reachableByFlows(logicalProcessingCalls.argument(2))
    .l
    .map(_.elements.collect { case node: nodes.AstNode => node })
    .filter(isSimplePath)
  val dependencyPaths = logicalProcessingCalls.argument
    .reachableByFlows(logicalProcessingCalls)
    .l
    .map(_.elements.collect { case node: nodes.AstNode => node })
    .filter(isSimplePath)
  val processingTerminalPaths = cpg.ret
    .reachableByFlows(logicalProcessingCalls)
    .l
    .map(_.elements.collect { case node: nodes.AstNode => node })
    .filter(isSimplePath)

  val processingCalls = logicalProcessingCalls.l.sortBy(call => (
    call.lineNumber.getOrElse(Int.MaxValue),
    call.columnNumber.getOrElse(Int.MaxValue),
    call.id
  ))
  val operatorIds = processingCalls.flatMap { call =>
    call.argument.l.collect {
      case literal: nodes.Literal if literal.argumentIndex == 1 => literal.code
    }.headOption.map(unquote).filter(isOperatorId)
  }.distinct
  val processingTerminals: Seq[nodes.AstNode] = cpg.ret.l
    .filter(_.lineNumber.isDefined)
    .map(node => node: nodes.AstNode)
  val processingComplete = operatorIds.size >= 2 &&
    operatorPaths.nonEmpty && helperPaths.nonEmpty && parameterPaths.nonEmpty &&
    dependencyPaths.nonEmpty && processingTerminals.nonEmpty

  def apiCalls = cpg.call.filter(call => ApiSourceNames.contains(call.name))
  def transformCalls = cpg.call.filter(call => ApiTransformNames.contains(call.name))
  def mutationCalls = cpg.call.name("setGeometry")
  def sinkCalls = cpg.call.name("addFeature|addFeatures|writeAsVectorFormatV3")
  val mutationPaths = mutationCalls.argument
    .reachableByFlows(apiCalls)
    .l
    .map(_.elements.collect { case node: nodes.AstNode => node })
    .filter(isSimplePath)
  val sinkPaths = sinkCalls.argument
    .reachableByFlows(transformCalls)
    .l
    .map(_.elements.collect { case node: nodes.AstNode => node })
    .filter(isSimplePath)
  val transformNames = mutationPaths.flatMap(_.collect {
    case call: nodes.Call if ApiTransformNames.contains(call.name) => call.name
  }).distinct.sorted
  val semanticCalls = cpg.call.l
    .filter(call => ApiSourceNames.contains(call.name) || ApiTerminalNames.contains(call.name))
    .sortBy(call => (
      call.lineNumber.getOrElse(Int.MaxValue),
      call.columnNumber.getOrElse(Int.MaxValue),
      call.id
    ))
    .map(_.name)
  val apiTerminals: Seq[nodes.AstNode] = sinkCalls.l
    .filter(_.lineNumber.isDefined)
    .map(node => node: nodes.AstNode)
  val controls: Seq[nodes.AstNode] = cpg.controlStructure.l
    .filter(_.lineNumber.isDefined)
    .map(node => node: nodes.AstNode)
  val apiAmbiguous = transformNames.size > 1
  val apiComplete = transformNames.size == 1 && mutationPaths.nonEmpty &&
    sinkPaths.nonEmpty && apiTerminals.nonEmpty

  val (evidenceStatus, queries, selectedPaths, terminals, ambiguityReasons) = corpusKind match {
    case "processing" =>
      val status = if (processingComplete) "complete" else "insufficient"
      val queryStatus = if (processingComplete) "complete" else "insufficient"
      val rows = Seq(
        queryJson("P1", queryStatus, operatorPaths, Seq.empty, processingTerminals, Seq("operator_id_dataflow")),
        queryJson("P2", queryStatus, parameterPaths, Seq.empty, processingTerminals, Seq("parameter_dictionary_dataflow")),
        queryJson("P3", queryStatus, dependencyPaths, Seq.empty, processingTerminals, Seq("output_alias_dependency")),
        queryJson("P4", queryStatus, helperPaths, Seq.empty, processingTerminals, Seq("caller_callee_parameter_return")),
        queryJson("P5", queryStatus, processingTerminalPaths, Seq.empty, processingTerminals, Seq("terminal_path"))
      )
      (status, rows, operatorPaths ++ parameterPaths ++ dependencyPaths ++ helperPaths ++ processingTerminalPaths, processingTerminals, Seq.empty[String])
    case "api" =>
      val status = if (apiAmbiguous) "ambiguous" else if (apiComplete) "complete" else "insufficient"
      val baseStatus = if (apiComplete || apiAmbiguous) "complete" else "insufficient"
      val a5Status = if (apiAmbiguous) "ambiguous" else baseStatus
      val rows = Seq(
        queryJson("A1", baseStatus, mutationPaths, controls, apiTerminals, Seq("semantic_api_source")),
        queryJson("A2", baseStatus, mutationPaths ++ sinkPaths, controls, apiTerminals, Seq("mutation_and_sink_dataflow")),
        queryJson("A3", baseStatus, sinkPaths, controls, apiTerminals, Seq("parameter_and_return_propagation")),
        queryJson("A4", baseStatus, sinkPaths, controls, apiTerminals, Seq("terminal_backward_slice")),
        queryJson("A5", a5Status, mutationPaths, controls, apiTerminals, Seq("branch_conflict_check"))
      )
      val reasons = if (apiAmbiguous) Seq("incompatible_branch_definitions") else Seq.empty[String]
      (status, rows, mutationPaths ++ sinkPaths, apiTerminals, reasons)
  }

  val evidenceNodes: Seq[nodes.AstNode] = (
    selectedPaths.flatten ++ terminals ++ controls
  ).filter(_.lineNumber.exists(_ > 0)).distinctBy(_.id).sortBy(node => (
    node.lineNumber.getOrElse(Int.MaxValue),
    node.columnNumber.getOrElse(Int.MaxValue),
    node.id
  ))
  require(
    evidenceStatus == "insufficient" || evidenceNodes.nonEmpty,
    "non-insufficient query produced no source-grounded evidence nodes"
  )

  val dependencyEdges = if (
    corpusKind == "processing" && operatorIds.size == 2 && dependencyPaths.nonEmpty
  ) {
    ujson.Arr(ujson.Arr(ujson.Num(0), ujson.Num(1)))
  } else {
    ujson.Arr()
  }

  val record = ujson.Obj(
    "record_id" -> ujson.Str(recordId),
    "source_sha256" -> ujson.Str(sourceSha256.toLowerCase),
    "corpus_kind" -> ujson.Str(corpusKind),
    "query_version" -> ujson.Str("qgis-flow-v1"),
    "evidence_status" -> ujson.Str(evidenceStatus),
    "nodes" -> ujson.Arr.from(evidenceNodes.map(node => nodeJson(node, sourcePath))),
    "queries" -> ujson.Arr.from(queries),
    "operator_ids" -> ujson.Arr.from(if (corpusKind == "processing") operatorIds.map(ujson.Str(_)) else Seq.empty),
    "semantic_calls" -> ujson.Arr.from(if (corpusKind == "api") semanticCalls.map(ujson.Str(_)) else Seq("processing.run").map(ujson.Str(_))),
    "dependency_edges" -> dependencyEdges,
    "ambiguity_reasons" -> ujson.Arr.from(ambiguityReasons.map(ujson.Str(_)))
  )

  Files.writeString(
    java.nio.file.Path.of(outputPath),
    ujson.write(record, indent = -1, escapeUnicode = false) + "\n",
    StandardCharsets.UTF_8
  )
}
