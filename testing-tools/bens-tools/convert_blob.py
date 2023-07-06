import blob
import sys

if len(sys.argv) < 2:
    print("Please provide the input file name as the first argument.")
    sys.exit(1)

input_file = sys.argv[1]
unserialized_blob = blob.load_from_file(input_file)

blob_data = blob.dump_to_dict(unserialized_blob)

output_file = input_file.rsplit(".", 1)[0] + ".py"
with open(output_file, "w") as f:
    f.write('blob = ' + blob_data)
