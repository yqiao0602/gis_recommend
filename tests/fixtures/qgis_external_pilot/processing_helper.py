import processing


def run_algorithm(algorithm_id, parameters):
    return processing.run(algorithm_id, parameters)


def build_workflow(input_layer):
    buffered = run_algorithm(
        "native:buffer",
        {"INPUT": input_layer, "DISTANCE": 10, "OUTPUT": "TEMPORARY_OUTPUT"},
    )
    buffer_output = buffered["OUTPUT"]
    return run_algorithm(
        "native:dissolve",
        {"INPUT": buffer_output, "OUTPUT": "TEMPORARY_OUTPUT"},
    )
